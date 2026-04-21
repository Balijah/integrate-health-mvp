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
SYSTEM_PROMPT = """You are an expert medical documentation assistant specializing in functional medicine. Generate comprehensive SOAP notes from patient visit transcripts.

CRITICAL RULES:
- Only include information explicitly mentioned in the transcript or contextual notes
- Never invent, infer, or hallucinate clinical details not present in the source material
- Omit any JSON key entirely if the information was not mentioned — do not use empty strings or empty arrays
- Always use the patient's preferred gender pronouns throughout
- For all dosages and frequencies, always use numerals (e.g., "10 mg twice daily" not "ten milligrams two times a day")
- For supplements, always include the exact number of capsules or scoops discussed
- The plan section must be a comprehensive summary of ALL interventions discussed — systematically review every issue in clinical_discussion and ensure nothing is missed

Respond with ONLY valid JSON. No text before or after."""

USER_PROMPT_TEMPLATE = """Generate a SOAP note from the following patient visit transcript.

{additional_context_block}TRANSCRIPT:
{transcript}

Generate the SOAP note in this exact JSON structure. Omit any key for which no information was mentioned — do not include empty strings or empty arrays:

```json
{{
  "subjective": {{
    "reason_for_visit": "Primary reason the patient came in today",
    "history_of_present_illness": "Detailed narrative of current symptoms, onset, duration, and progression",
    "review_of_systems": "Pertinent positive and negative findings across body systems",
    "past_medical_history": "Relevant diagnoses, surgeries, hospitalizations",
    "current_medications": ["Medication name, dose, and frequency for each current prescription"],
    "current_supplements": ["Supplement name, dose, and frequency for each supplement currently taken"],
    "allergies": ["Allergen and reaction type"],
    "social_history": "Lifestyle factors: diet, exercise, sleep, stress, occupation, substance use",
    "family_history": "Relevant family medical conditions"
  }},
  "objective": {{
    "vitals": {{
      "blood_pressure": "systolic/diastolic mmHg",
      "heart_rate": "bpm",
      "temperature": "degrees F or C",
      "weight": "lbs or kg",
      "height": "ft/in or cm",
      "bmi": "numeric value"
    }},
    "physical_exam": "Relevant physical examination findings",
    "lab_results": "Lab values reviewed during this visit with reference ranges where mentioned"
  }},
  "assessment": {{
    "diagnoses": ["Primary diagnosis or impression", "Additional diagnoses if mentioned"],
    "clinical_discussion": [
      {{
        "issue": "Name of the clinical issue or symptom discussed",
        "findings": "Relevant findings, lab values, or patient-reported data for this issue",
        "interpretation": "Clinical interpretation or root-cause reasoning",
        "plan_summary": "Brief summary of the plan for this specific issue"
      }}
    ],
    "clinical_reasoning": "Overall root-cause analysis tying all issues together"
  }},
  "plan": {{
    "prescriptions": {{
      "add": ["New prescription: medication name, dose, frequency, and any special instructions"],
      "continue": ["Continuing prescription: medication name, dose, frequency"],
      "discontinue": ["Discontinued prescription: medication name and reason if stated"]
    }},
    "supplements": {{
      "add": ["New supplement: name, dose (capsules/scoops/mg), frequency, and timing"],
      "continue": ["Continuing supplement: name, dose, frequency"],
      "discontinue": ["Discontinued supplement: name and reason if stated"]
    }},
    "lab_orders": ["Test name and clinical indication"],
    "imaging_or_referrals": ["Imaging ordered or referral made, with reason"],
    "lifestyle_recommendations": "Specific diet, exercise, sleep, and stress management instructions given",
    "patient_education": "Topics discussed and key points communicated to the patient",
    "follow_up": "Follow-up timeframe and conditions for return visit"
  }}
}}
```

Respond with ONLY the JSON object, no additional text."""


def _get_bedrock_client():
    """Get boto3 Bedrock Runtime client."""
    settings = get_settings()
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


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
