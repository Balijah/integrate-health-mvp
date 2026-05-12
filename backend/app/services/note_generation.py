"""
SOAP Note generation service using AWS Bedrock.

Generates structured SOAP notes from visit transcripts using Claude models
via AWS Bedrock.
"""

import json
import logging
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from app.config import get_settings

logger = logging.getLogger(__name__)


class NoteGenerationError(Exception):
    """Custom exception for note generation failures."""
    pass


# System prompt for functional medicine SOAP note generation
SYSTEM_PROMPT = """You are an expert medical documentation assistant specializing in functional, integrative, and longevity medicine. Generate comprehensive, provider-ready SOAP notes from patient visit transcripts.

Your primary goal is clinical completeness. Providers using this note want confidence that the full visit was captured, including nuanced details, patient-reported observations, supplement changes, treatment responses, relevant history, and clinical reasoning.

--------------------------------------------------
CORE RULES
--------------------------------------------------

- Only include information explicitly stated in the transcript or provided context.
- Never invent, assume, or hallucinate clinical details.
- Omit any field entirely if information is not present.
- Do not use empty strings, null values, placeholders, or bracketed instructions.
- Use the patient's preferred gender pronouns throughout.
- Use precise medical language, but preserve patient-reported wording when clinically meaningful.
- Use numerals for all dosages and frequencies, e.g., "10 mg twice daily."
- For medications and supplements, include name, dose, frequency, adherence pattern, reason for use, and reason for stopping or changing when mentioned.
- Prioritize completeness and clinical safety over brevity.
- Do not over-compress the patient story.

--------------------------------------------------
DOCUMENTATION STYLE
--------------------------------------------------

The note should feel detailed, thorough, and clinically safe, similar to a high-quality human scribe note, but more organized.

Capture:
- Chronology of symptoms and events
- Severity ratings
- Patient-reported changes over time
- Treatment attempts and responses
- Medication and supplement changes
- Pertinent negatives
- Functional impact
- Relevant medical history
- Relevant family, social, lifestyle, environmental, and exposure history
- Provider recommendations and patient education
- Follow-up plans and testing discussed

Do not include irrelevant small talk or non-clinical conversation, but when in doubt, include patient-specific details that may help clinical interpretation.

--------------------------------------------------
SUBJECTIVE SECTION REQUIREMENTS
--------------------------------------------------

The Subjective section should be comprehensive.

History of Present Illness:
- Write a detailed chronological narrative.
- Preserve symptom onset, progression, duration, severity, triggers, relieving factors, and functional impact.
- Include patient-reported observations and theories when relevant.
- Include context around why medications, supplements, or protocols were started, stopped, increased, decreased, or changed.
- Preserve important anecdotal details if they illustrate severity or clinical relevance.

Review of Systems:
- Must be returned as a single plain string, not a JSON object.
- Format as "System: findings" entries separated by newlines (e.g., "Constitutional: fatigue\nNeurological: headaches").
- Structure by body system when symptoms are discussed.
- Include both positives and clinically relevant negatives when mentioned.
- Use categories such as:
  constitutional, neurological, cardiovascular, respiratory, gastrointestinal, genitourinary, musculoskeletal, skin, psychiatric, endocrine, sleep, HEENT.
- Only include systems explicitly discussed.

Relevant History and Trends:
- Include a dedicated summary of important longitudinal context when present.
- Capture prior abnormal labs, trends, chronic conditions, prior treatments, procedures, hospitalizations, exposures, and prior responses to therapy.
- This section should be detailed enough to support functional medicine decision-making.

Detailed Clinical Context:
- Include when substantial background information is discussed.
- Capture lifestyle, diet, environmental exposures, water quality, mold/toxin concerns, occupational factors, stressors, patient preferences, and patient-reported patterns.
- Organize clearly rather than dumping information.

--------------------------------------------------
OBJECTIVE SECTION REQUIREMENTS
--------------------------------------------------

Include all objective findings explicitly mentioned, including:
- Vitals
- Physical exam observations
- Lab results
- Imaging
- Prior testing
- Procedure history
- Specialist visits
- Patient-provided results

Lab results:
- Preserve actual values, trends, and comparisons when mentioned.
- Do not generalize abnormal labs if specific values or trends were stated.
- If labs were reviewed but values were not stated, summarize the abnormalities exactly as discussed.

--------------------------------------------------
ASSESSMENT SECTION REQUIREMENTS
--------------------------------------------------

Diagnoses:
- Include all diagnoses, suspected diagnoses, active clinical issues, and clinically relevant abnormal findings discussed.
- Include chronic conditions and active problems when they affect the visit.

Key Clinical Signals:
- Include a dedicated list of important clinical risks, red flags, or high-priority signals when present.
- Examples include possible TIA/stroke symptoms, active bleeding, abnormal blood counts, elevated liver enzymes, worsening cognitive symptoms, recurrent arrhythmia, dehydration, or significant abnormal lab trends.
- Focus on clinically meaningful signals, not every symptom.

Clinical Discussion:
- Use a problem-based format.
- Each issue should include:
  - findings: detailed supporting details from the visit
  - interpretation: clinical meaning, concern, differential, or provider impression when discussed
  - plan_summary: what was recommended or planned for that issue
- Include all relevant supporting details, even if the note becomes longer.
- Do not collapse multiple important problems into one vague issue.

Clinical Reasoning:
- Explicitly connect symptoms, timeline, risk factors, labs, medications, supplements, and treatment decisions.
- Include differential considerations when discussed.
- Preserve uncertainty when present.
- Do not state certainty where the transcript only supports concern, suspicion, or possibility.

--------------------------------------------------
PLAN SECTION REQUIREMENTS
--------------------------------------------------

The Plan must be complete and actionable.

Systematically review every issue in the Clinical Discussion and ensure every recommendation is captured.

Separate plan items into:
- prescriptions: add, continue, discontinue, change
- supplements: add, continue, discontinue, change
- labs
- imaging
- referrals
- procedures
- lifestyle recommendations
- nutrition recommendations
- patient education
- follow-up

For every medication or supplement change, include the reason when mentioned.

For labs, imaging, referrals, or procedures:
- Include timing, location, purpose, and next step when discussed.

For lifestyle and nutrition:
- Include specific recommendations discussed, not generic wellness advice.

For patient education:
- Include explanations given to the patient, warnings, monitoring instructions, and when to seek urgent care when discussed.

--------------------------------------------------
FUNCTIONAL MEDICINE SPECIFIC REQUIREMENTS
--------------------------------------------------

Because these visits may include complex functional medicine care, pay close attention to:

- Supplements and protocols
- Detoxification regimens
- Heavy metals
- Mycotoxins
- Mold exposure
- Hormone trends
- Thyroid management
- Gut health, parasites, fungal concerns, dysbiosis
- Inflammation markers
- Nutritional deficiencies
- Environmental exposures
- Medication/supplement interactions
- Patient-reported treatment responses

Do not dismiss or omit functional medicine context simply because it is not conventional documentation.

--------------------------------------------------
OUTPUT FORMAT
--------------------------------------------------

Respond with ONLY valid JSON.

No markdown.
No explanation.
No commentary before or after the JSON.
No placeholder text.
No bracketed field descriptions.
No `[object Object]`.

Use the exact schema requested in the user prompt.
Omit unavailable keys entirely rather than returning empty values.

--------------------------------------------------
FINAL QUALITY CHECK
--------------------------------------------------

Before responding, verify:

- The note captures all clinically relevant details from the transcript.
- The HPI is detailed enough to preserve the patient story.
- ROS is a single plain string (not a JSON object) organized by body system.
- Relevant history and trends are included when present.
- Key clinical signals are clearly visible.
- Labs and historical values are preserved when mentioned.
- Medication and supplement changes include reasons when available.
- The plan addresses every issue in the assessment.
- No invented details were added.
- The note is comprehensive, organized, and provider-ready.

The final note should feel thorough enough that a provider reviewing it later would not need to return to the transcript to understand what happened during the visit."""

USER_PROMPT_TEMPLATE = """Generate a SOAP note from the following patient visit transcript.

{additional_context_block}TRANSCRIPT:
{transcript}

IMPORTANT: Values shown in [brackets] below are field descriptions only — never output bracket text. Omit any key for which the transcript contains no information.

```json
{{
  "subjective": {{
    "reason_for_visit": "[omit if not mentioned]",
    "history_of_present_illness": "[omit if not mentioned]",
    "review_of_systems": "[omit if not mentioned]",
    "past_medical_history": "[omit if not mentioned]",
    "current_medications": ["[name, dose, frequency — omit array if none mentioned]"],
    "current_supplements": ["[name, dose, frequency — omit array if none mentioned]"],
    "allergies": ["[allergen and reaction — omit array if none mentioned]"],
    "social_history": "[omit if not mentioned]",
    "family_history": "[omit if not mentioned]"
  }},
  "objective": {{
    "vitals": {{
      "blood_pressure": "[omit if not mentioned]",
      "heart_rate": "[omit if not mentioned]",
      "temperature": "[omit if not mentioned]",
      "weight": "[omit if not mentioned]",
      "height": "[omit if not mentioned]",
      "bmi": "[omit if not mentioned]"
    }},
    "physical_exam": "[omit if not mentioned]",
    "lab_results": "[omit if not mentioned]"
  }},
  "assessment": {{
    "diagnoses": ["[diagnosis — omit array if none mentioned]"],
    "clinical_discussion": [
      {{
        "issue": "[clinical issue]",
        "findings": "[omit if not mentioned]",
        "interpretation": "[omit if not mentioned]",
        "plan_summary": "[omit if not mentioned]"
      }}
    ],
    "clinical_reasoning": "[omit if not mentioned]"
  }},
  "plan": {{
    "prescriptions": {{
      "add": ["[omit array if none]"],
      "continue": ["[omit array if none]"],
      "discontinue": ["[omit array if none]"]
    }},
    "supplements": {{
      "add": ["[omit array if none]"],
      "continue": ["[omit array if none]"],
      "discontinue": ["[omit array if none]"]
    }},
    "lab_orders": ["[test and indication — omit array if none]"],
    "imaging_or_referrals": ["[imaging or referral and reason — omit array if none]"],
    "lifestyle_recommendations": "[omit if not mentioned]",
    "patient_education": "[omit if not mentioned]",
    "follow_up": "[omit if not mentioned]"
  }}
}}
```

Respond with ONLY the JSON object, no additional text."""


def _get_bedrock_client():
    """Get boto3 Bedrock Runtime client with extended timeouts for long transcripts."""
    from botocore.config import Config
    settings = get_settings()
    config = Config(
        read_timeout=300,    # 5 minutes — long transcripts can take 2-3 min on cross-region inference
        connect_timeout=10,
        retries={"max_attempts": 1},
    )
    return boto3.client("bedrock-runtime", region_name=settings.aws_region, config=config)


def _normalize_ros(value) -> str:
    """Convert a ROS dict (returned by Bedrock) to a plain readable string."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for system, text in value.items():
            label = system.replace("_", " ").title()
            parts.append(f"{label}: {text}")
        return "\n".join(parts)
    return str(value)


def _extract_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from Claude's response, handling various formats.

    Claude may return JSON wrapped in markdown code blocks or with extra text.
    This function attempts multiple strategies to extract valid JSON.

    Args:
        response_text: The raw response text from Claude.

    Returns:
        Parsed JSON as a dict.

    Raises:
        json.JSONDecodeError: If no valid JSON could be extracted.
    """
    # Strategy 1: Try parsing directly
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code blocks (```json ... ``` or ``` ... ```)
    code_block_patterns = [
        r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
        r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
    ]

    for pattern in code_block_patterns:
        match = re.search(pattern, response_text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find JSON object by locating first { and last }
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        potential_json = response_text[first_brace:last_brace + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            pass

    # Strategy 4: Strip common prefixes/suffixes and try again
    cleaned = response_text.strip()
    for prefix in ["Here is the SOAP note:", "Here's the SOAP note:", "SOAP Note:"]:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # If all strategies fail, raise the original error
    raise json.JSONDecodeError("Could not extract valid JSON from response", response_text, 0)


def generate_soap_note(transcript: str, additional_context: str = "") -> dict:
    """
    Generate a SOAP note from a transcript using AWS Bedrock.

    Args:
        transcript: The visit transcript text.
        additional_context: Optional additional context (patient history, etc.).

    Returns:
        dict containing the structured SOAP note content.

    Raises:
        NoteGenerationError: If generation fails.
    """
    settings = get_settings()

    if not transcript or not transcript.strip():
        raise NoteGenerationError("Transcript is empty. Cannot generate note.")

    try:
        # Initialize Bedrock client
        bedrock = _get_bedrock_client()

        # Build additional context block
        if additional_context and additional_context.strip():
            additional_context_block = f"ADDITIONAL CONTEXT:\n{additional_context}\n\n"
        else:
            additional_context_block = ""

        user_prompt = USER_PROMPT_TEMPLATE.format(
            additional_context_block=additional_context_block,
            transcript=transcript,
        )

        # Prepare request body for Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": settings.bedrock_max_tokens,
            "temperature": settings.bedrock_temperature,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
        }

        # Log full request before sending
        logger.info(
            f"[BEDROCK REQUEST] model={settings.bedrock_model_id} "
            f"max_tokens={settings.bedrock_max_tokens} temperature={settings.bedrock_temperature} "
            f"transcript_len={len(transcript)} context_len={len(additional_context_block)}"
        )
        logger.info(f"[BEDROCK SYSTEM PROMPT]\n{SYSTEM_PROMPT}")
        logger.info(f"[BEDROCK USER PROMPT]\n{user_prompt}")

        response = bedrock.invoke_model(
            modelId=settings.bedrock_model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # Parse response
        response_body = json.loads(response["body"].read())

        # Extract response text and strip any code fences the model may include
        response_text = response_body["content"][0]["text"]
        response_text = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", response_text.strip(), flags=re.MULTILINE
        )

        # Capture token usage from Bedrock response
        usage = response_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        logger.info(
            f"[BEDROCK RESPONSE] input_tokens={input_tokens} output_tokens={output_tokens} "
            f"response_len={len(response_text)}"
        )
        logger.info(f"[BEDROCK RAW RESPONSE]\n{response_text}")

        # Parse JSON response - handle potential markdown code blocks or extra text
        try:
            soap_content = _extract_json_from_response(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"[BEDROCK] Failed to parse response as JSON (length={len(response_text)}): {e}")
            logger.error(f"[BEDROCK RAW UNPARSEABLE RESPONSE]\n{response_text}")
            raise NoteGenerationError(f"Failed to parse generated note: {str(e)}")

        # Coerce review_of_systems to a string if Bedrock returned a dict
        subj = soap_content.get("subjective")
        if isinstance(subj, dict) and isinstance(subj.get("review_of_systems"), dict):
            subj["review_of_systems"] = _normalize_ros(subj["review_of_systems"])

        # Validate that at least one SOAP section is present
        soap_keys = {"subjective", "objective", "assessment", "plan"}
        if not soap_keys.intersection(soap_content.keys()):
            logger.error(f"[BEDROCK] Response has no SOAP sections. Keys={list(soap_content.keys())}")
            logger.error(f"[BEDROCK RAW EMPTY RESPONSE]\n{response_text}")
            raise NoteGenerationError(
                "The transcript did not contain enough clinical content to generate a note. "
                "Please record a visit with clinical details and try again."
            )

        # Add metadata including token usage
        soap_content["metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": settings.bedrock_model_id,
            "confidence_score": None,  # Could be enhanced with confidence estimation
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }

        logger.info("SOAP note generated successfully")
        return soap_content

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", "Unknown error")

        if error_code == "ThrottlingException":
            logger.error(f"Bedrock API rate limit exceeded: {error_message}")
            raise NoteGenerationError("AI service rate limit exceeded. Please try again later.")
        elif error_code == "AccessDeniedException":
            logger.error(f"Bedrock access denied: {error_message}")
            raise NoteGenerationError("AI service access denied. Check IAM permissions.")
        elif error_code == "ModelNotReadyException":
            logger.error(f"Bedrock model not ready: {error_message}")
            raise NoteGenerationError("AI model not available. Please try again.")
        else:
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise NoteGenerationError("AI service error. Please try again.")

    except BotoCoreError as e:
        logger.error(f"Failed to connect to Bedrock: {str(e)}")
        raise NoteGenerationError("Failed to connect to AI service. Please try again.")

    except Exception as e:
        logger.error(f"Unexpected error generating note: {type(e).__name__}: {str(e)}")
        raise NoteGenerationError("Failed to generate note. Please try again.")


def format_note_as_markdown(content: dict) -> str:
    """
    Format a SOAP note as markdown text.

    Args:
        content: SOAP note content dict.

    Returns:
        Formatted markdown string.
    """
    lines = ["# SOAP Note", ""]

    # Subjective
    subj = content.get("subjective", {})
    lines.append("## Subjective")
    lines.append("")
    lines.append(f"**Chief Complaint:** {subj.get('chief_complaint', 'N/A')}")
    lines.append("")
    lines.append(f"**History of Present Illness:** {subj.get('history_of_present_illness', 'N/A')}")
    lines.append("")

    if subj.get("review_of_systems"):
        lines.append(f"**Review of Systems:** {subj['review_of_systems']}")
        lines.append("")

    if subj.get("past_medical_history"):
        lines.append(f"**Past Medical History:** {subj['past_medical_history']}")
        lines.append("")

    if subj.get("medications"):
        lines.append("**Current Medications:**")
        for med in subj["medications"]:
            lines.append(f"- {med}")
        lines.append("")

    if subj.get("supplements"):
        lines.append("**Current Supplements:**")
        for supp in subj["supplements"]:
            lines.append(f"- {supp}")
        lines.append("")

    if subj.get("allergies"):
        lines.append("**Allergies:**")
        for allergy in subj["allergies"]:
            lines.append(f"- {allergy}")
        lines.append("")

    if subj.get("social_history"):
        lines.append(f"**Social History:** {subj['social_history']}")
        lines.append("")

    if subj.get("family_history"):
        lines.append(f"**Family History:** {subj['family_history']}")
        lines.append("")

    # Objective
    obj = content.get("objective", {})
    lines.append("## Objective")
    lines.append("")

    vitals = obj.get("vitals", {})
    vitals_parts = []
    if vitals.get("blood_pressure"):
        vitals_parts.append(f"BP: {vitals['blood_pressure']}")
    if vitals.get("heart_rate"):
        vitals_parts.append(f"HR: {vitals['heart_rate']}")
    if vitals.get("temperature"):
        vitals_parts.append(f"Temp: {vitals['temperature']}")
    if vitals.get("weight"):
        vitals_parts.append(f"Weight: {vitals['weight']}")

    if vitals_parts:
        lines.append(f"**Vitals:** {', '.join(vitals_parts)}")
        lines.append("")

    if obj.get("physical_exam"):
        lines.append(f"**Physical Exam:** {obj['physical_exam']}")
        lines.append("")

    if obj.get("lab_results"):
        lines.append(f"**Lab Results:** {obj['lab_results']}")
        lines.append("")

    # Assessment
    assess = content.get("assessment", {})
    lines.append("## Assessment")
    lines.append("")

    if assess.get("diagnoses"):
        lines.append("**Diagnoses:**")
        for i, dx in enumerate(assess["diagnoses"], 1):
            lines.append(f"{i}. {dx}")
        lines.append("")

    if assess.get("clinical_reasoning"):
        lines.append(f"**Clinical Reasoning:** {assess['clinical_reasoning']}")
        lines.append("")

    # Plan
    plan = content.get("plan", {})
    lines.append("## Plan")
    lines.append("")

    if plan.get("treatment_plan"):
        lines.append(f"**Treatment Plan:** {plan['treatment_plan']}")
        lines.append("")

    if plan.get("medications_prescribed"):
        lines.append("**Medications Prescribed:**")
        for med in plan["medications_prescribed"]:
            lines.append(f"- {med}")
        lines.append("")

    if plan.get("supplements_recommended"):
        lines.append("**Supplements Recommended:**")
        for supp in plan["supplements_recommended"]:
            lines.append(f"- {supp}")
        lines.append("")

    if plan.get("lifestyle_recommendations"):
        lines.append(f"**Lifestyle Recommendations:** {plan['lifestyle_recommendations']}")
        lines.append("")

    if plan.get("lab_orders"):
        lines.append("**Lab Orders:**")
        for lab in plan["lab_orders"]:
            lines.append(f"- {lab}")
        lines.append("")

    if plan.get("follow_up"):
        lines.append(f"**Follow-up:** {plan['follow_up']}")
        lines.append("")

    if plan.get("patient_education"):
        lines.append(f"**Patient Education:** {plan['patient_education']}")
        lines.append("")

    # Metadata
    meta = content.get("metadata", {})
    if meta.get("generated_at"):
        lines.append("---")
        lines.append(f"*Generated: {meta['generated_at']}*")
        lines.append(f"*Model: {meta.get('model_version', 'N/A')}*")

    return "\n".join(lines)


def format_note_as_text(content: dict) -> str:
    """
    Format a SOAP note as plain text.

    Args:
        content: SOAP note content dict.

    Returns:
        Formatted plain text string.
    """
    # Use markdown format but strip markdown syntax
    markdown = format_note_as_markdown(content)

    # Simple conversion: remove markdown formatting
    text = markdown.replace("# ", "").replace("## ", "\n").replace("**", "")
    text = text.replace("- ", "  - ")

    return text


# Cost calculation constants (AWS Bedrock pricing as of 2024)
# Claude 3 Sonnet on Bedrock pricing
BEDROCK_SONNET_INPUT_COST_PER_MILLION = 3.00  # $3 per 1M input tokens
BEDROCK_SONNET_OUTPUT_COST_PER_MILLION = 15.00  # $15 per 1M output tokens

# Whisper self-hosted (approximate based on GPU costs)
# g4dn.xlarge Spot: ~$0.19/hour, can process ~60 min audio/hour
WHISPER_COST_PER_MINUTE = 0.0032  # ~$0.19/60 minutes


def calculate_bedrock_cost(input_tokens: int, output_tokens: int) -> dict:
    """
    Calculate the cost of a Bedrock API call.

    Args:
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.

    Returns:
        dict with input_cost, output_cost, and total_cost in USD.
    """
    input_cost = (input_tokens / 1_000_000) * BEDROCK_SONNET_INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * BEDROCK_SONNET_OUTPUT_COST_PER_MILLION
    total_cost = input_cost + output_cost

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
    }


def calculate_whisper_cost(duration_minutes: float) -> dict:
    """
    Calculate the estimated cost of Whisper transcription.

    Args:
        duration_minutes: Audio duration in minutes.

    Returns:
        dict with duration and cost in USD.
    """
    cost = duration_minutes * WHISPER_COST_PER_MINUTE

    return {
        "duration_minutes": duration_minutes,
        "cost_usd": round(cost, 4),
    }


def estimate_total_visit_cost(
    input_tokens: int,
    output_tokens: int,
    audio_duration_minutes: float | None = None,
) -> dict:
    """
    Estimate the total cost of processing a visit.

    Args:
        input_tokens: Bedrock input tokens.
        output_tokens: Bedrock output tokens.
        audio_duration_minutes: Optional audio duration for Whisper cost.

    Returns:
        dict with detailed cost breakdown.
    """
    bedrock_costs = calculate_bedrock_cost(input_tokens, output_tokens)

    result = {
        "bedrock": bedrock_costs,
        "whisper": None,
        "total_cost_usd": bedrock_costs["total_cost_usd"],
    }

    if audio_duration_minutes is not None:
        whisper_costs = calculate_whisper_cost(audio_duration_minutes)
        result["whisper"] = whisper_costs
        result["total_cost_usd"] = round(
            bedrock_costs["total_cost_usd"] + whisper_costs["cost_usd"], 4
        )

    return result
