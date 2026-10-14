"""
SOAP Note generation service using AWS Bedrock.

Generates structured SOAP notes from visit transcripts using Claude models
via AWS Bedrock.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, BotoCoreError, EventStreamError

from app.config import get_settings

logger = logging.getLogger(__name__)

_bedrock_client = None
_bedrock_client_lock = threading.Lock()
_bedrock_client_region: str | None = None


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
- Only document diagnoses, interpretations, causal links, differentials, warnings, and recommendations that the clinician explicitly stated.
- Do not add a rationale, purpose, or indication to an order or recommendation unless the clinician explicitly stated it.
- Omit any field entirely if information is not present.
- Do not use empty strings, null values, placeholders, or bracketed instructions.
- Use the patient's preferred gender pronouns throughout.
- Use precise medical language, but preserve patient-reported wording when clinically meaningful.
- Use numerals for all dosages and frequencies, e.g., "10 mg twice daily."
- For medications and supplements, include name, dose, frequency, adherence pattern, reason for use, and reason for stopping or changing when mentioned.
- Preserve every unique clinical fact, but do not repeat the same fact within a section.
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
- Populate interpretation only when the clinician explicitly states that interpretation. If the clinician names an issue without explaining its meaning or cause, omit interpretation.
- In plan_summary, preserve the clinician's action without supplying an unstated reason for it.
- Do not independently label a lab value high, low, abnormal, deficient, or suboptimal, and do not infer a diagnosis or cause from a value.
- Include all relevant supporting details, even if the note becomes longer.
- Do not collapse multiple important problems into one vague issue.

Clinical Reasoning:
- Include connections between symptoms, timeline, risk factors, labs, medications, supplements, and treatment decisions only when the clinician stated them.
- Omit clinical_reasoning entirely if the clinician did not voice those connections.
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
PATIENT-FACING SUMMARY REQUIREMENTS
--------------------------------------------------

In addition to the SOAP note, generate a patient_summary section at the same time, in the same JSON response.

This section is written for the patient, not the provider. It is a clean, professional, easy-to-read summary of the plan discussed during the visit.

Rules:
- Use plain, everyday language a patient can understand. Avoid clinical jargon.
- Keep the tone warm, professional, and clear.
- Use short bullet points.
- Focus on what the patient should DO next, not clinical reasoning.
- Do not include any recommendations that were not discussed in the transcript.
- Preserve exact medication and supplement names, doses, and instructions when provided.
- Group items into clean sections (plan_sections) using headings such as:
  Medications, Supplements, Labs & Testing, Imaging & Referrals, Lifestyle & Nutrition.
- Omit any section, bullet, or field that does not apply — never output empty values or placeholders.
- watch_for: symptoms, warning signs, or things the patient should monitor (omit if none discussed).
- follow_up: clear follow-up instructions such as next appointment timing (omit if none discussed).
- visit_summary: 1-3 warm, plain-language sentences summarizing today's visit.
- The patient should be able to read this and clearly understand their next steps.

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

# Static instruction prefix — identical across all requests and placed first
# in the user message so Anthropic prompt caching can store the system prompt
# plus this block as a reusable prefix (~2300 tokens saved on cache hits).
_USER_PROMPT_SCHEMA = """\
Generate a SOAP note from the patient visit transcript provided below.

IMPORTANT: Values shown in [brackets] below are field descriptions only — never output bracket text. Omit any key for which the transcript contains no information.

```json
{
  "subjective": {
    "reason_for_visit": "[omit if not mentioned]",
    "history_of_present_illness": "[omit if not mentioned]",
    "review_of_systems": "[omit if not mentioned]",
    "past_medical_history": "[omit if not mentioned]",
    "current_medications": ["[name, dose, frequency — omit array if none mentioned]"],
    "current_supplements": ["[name, dose, frequency — omit array if none mentioned]"],
    "allergies": ["[allergen and reaction — omit array if none mentioned]"],
    "social_history": "[omit if not mentioned]",
    "family_history": "[omit if not mentioned]"
  },
  "objective": {
    "vitals": {
      "blood_pressure": "[omit if not mentioned]",
      "heart_rate": "[omit if not mentioned]",
      "temperature": "[omit if not mentioned]",
      "weight": "[omit if not mentioned]",
      "height": "[omit if not mentioned]",
      "bmi": "[omit if not mentioned]"
    },
    "physical_exam": "[omit if not mentioned]",
    "lab_results": "[omit if not mentioned]"
  },
  "assessment": {
    "diagnoses": ["[diagnosis — omit array if none mentioned]"],
    "clinical_discussion": [
      {
        "issue": "[clinical issue]",
        "findings": "[omit if not mentioned]",
        "interpretation": "[omit if not mentioned]",
        "plan_summary": "[omit if not mentioned]"
      }
    ],
    "clinical_reasoning": "[omit if not mentioned]"
  },
  "plan": {
    "prescriptions": {
      "add": ["[omit array if none]"],
      "continue": ["[omit array if none]"],
      "discontinue": ["[omit array if none]"]
    },
    "supplements": {
      "add": ["[omit array if none]"],
      "continue": ["[omit array if none]"],
      "discontinue": ["[omit array if none]"]
    },
    "lab_orders": ["[test; include indication only if explicitly stated — omit array if none]"],
    "imaging_or_referrals": ["[imaging or referral; include reason only if explicitly stated — omit array if none]"],
    "lifestyle_recommendations": "[omit if not mentioned]",
    "patient_education": "[omit if not mentioned]",
    "follow_up": "[omit if not mentioned]"
  },
  "patient_summary": {
    "title": "Your Care Plan",
    "visit_summary": "[brief patient-friendly summary of today's visit]",
    "plan_sections": [
      {
        "heading": "[section heading, e.g. Medications, Supplements, Labs & Testing]",
        "items": ["[clear patient-facing bullet point]"]
      }
    ],
    "watch_for": ["[symptoms, warning signs, or things to monitor — omit array if none]"],
    "follow_up": ["[follow-up instructions — omit array if none]"]
  }
}
```

Respond with ONLY the JSON object, no additional text."""


def _get_bedrock_client():
    """Return a cached boto3 Bedrock Runtime client.

    The client is thread-safe and reused across calls to avoid the overhead of
    credential resolution, endpoint discovery, and HTTP session setup on every
    note generation request (~50-200 ms per cold creation).  A new client is
    created only on the first call or when the configured AWS region changes.
    """
    global _bedrock_client, _bedrock_client_region

    settings = get_settings()
    region = settings.aws_region

    if _bedrock_client is not None and _bedrock_client_region == region:
        return _bedrock_client

    with _bedrock_client_lock:
        if _bedrock_client is not None and _bedrock_client_region == region:
            return _bedrock_client

        from botocore.config import Config
        config = Config(
            read_timeout=600,
            connect_timeout=10,
            retries={"max_attempts": 1},
        )
        _bedrock_client = boto3.client(
            "bedrock-runtime", region_name=region, config=config,
        )
        _bedrock_client_region = region
        return _bedrock_client


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


def _coerce_to_list(val, section: str, field: str):
    """Ensure val is a list; wrap strings in a list and log a warning when coercing."""
    if val is None:
        return val
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        logger.warning(
            f"[SOAP COERCE] {section}.{field}: expected list, got 'str' — wrapping. "
            f"Value snippet: {val[:120]!r}"
        )
        return [val.strip()]
    logger.warning(
        f"[SOAP COERCE] {section}.{field}: expected list, got {type(val).__name__!r} — resetting to []. "
        f"Value: {str(val)[:120]!r}"
    )
    return []


def _normalize_soap_content(content: dict) -> dict:
    """
    Coerce AI-generated SOAP content to consistent field types.

    The model occasionally returns array fields as strings (e.g. allergies as a
    narrative string). This corrects those type mismatches before the note is
    saved, so the frontend always receives predictable types.
    """
    subj = content.get("subjective")
    if isinstance(subj, dict):
        for field in ("allergies", "current_medications", "current_supplements"):
            if field in subj:
                subj[field] = _coerce_to_list(subj[field], "subjective", field)

    assess = content.get("assessment")
    if isinstance(assess, dict):
        if "diagnoses" in assess:
            assess["diagnoses"] = _coerce_to_list(assess["diagnoses"], "assessment", "diagnoses")

    plan = content.get("plan")
    if isinstance(plan, dict):
        for field in ("lab_orders", "imaging_or_referrals"):
            if field in plan:
                plan[field] = _coerce_to_list(plan[field], "plan", field)

        rx = plan.get("prescriptions")
        if isinstance(rx, dict):
            for sub in ("add", "continue", "discontinue"):
                if sub in rx:
                    rx[sub] = _coerce_to_list(rx[sub], "plan.prescriptions", sub)

        supps = plan.get("supplements")
        if isinstance(supps, dict) and any(k in supps for k in ("add", "continue", "discontinue")):
            for sub in ("add", "continue", "discontinue"):
                if sub in supps:
                    supps[sub] = _coerce_to_list(supps[sub], "plan.supplements", sub)

    return content


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


def _invoke_bedrock_streaming(
    bedrock,
    model_id: str,
    system_blocks: list[dict],
    user_blocks: list[dict],
    *,
    max_tokens: int,
    temperature: float,
) -> dict:
    """Fire a single Bedrock streaming request and return parsed results.

    Returns a dict with keys: soap_content, input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens, duration_seconds,
    ttft_ms, streaming_ms, output_tokens_per_sec, stop_reason, client_init_ms,
    invoke_handshake_ms.

    Raises NoteGenerationError on empty responses or parse failures.
    """
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_blocks,
        "messages": [{"role": "user", "content": user_blocks}],
    }

    _generation_start = time.perf_counter()
    response = bedrock.invoke_model_with_response_stream(
        modelId=model_id,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )
    invoke_handshake_ms = round((time.perf_counter() - _generation_start) * 1000, 1)

    text_chunks: list[str] = []
    input_tokens = 0
    output_tokens = 0
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0
    stop_reason = None
    _first_token_at = None

    for event in response["body"]:
        chunk_bytes = event.get("chunk", {}).get("bytes")
        if not chunk_bytes:
            continue
        event_data = json.loads(chunk_bytes.decode("utf-8"))
        event_type = event_data.get("type")

        if event_type == "content_block_delta":
            delta = event_data.get("delta", {})
            if delta.get("type") == "text_delta":
                if _first_token_at is None:
                    _first_token_at = time.perf_counter()
                text_chunks.append(delta.get("text", ""))
        elif event_type == "message_start":
            usage = event_data.get("message", {}).get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0)
            cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)
        elif event_type == "message_delta":
            output_tokens = event_data.get("usage", {}).get("output_tokens", 0)
            stop_reason = event_data.get("delta", {}).get("stop_reason")

    _stream_end = time.perf_counter()
    response_text = "".join(text_chunks)
    duration_seconds = round(_stream_end - _generation_start, 2)

    ttft_ms = (
        round((_first_token_at - _generation_start) * 1000, 1)
        if _first_token_at is not None else None
    )
    streaming_ms = (
        round((_stream_end - _first_token_at) * 1000, 1)
        if _first_token_at is not None else None
    )
    output_tokens_per_sec = (
        round(output_tokens / (streaming_ms / 1000), 1)
        if streaming_ms and streaming_ms > 0 and output_tokens else None
    )

    if not response_text.strip():
        raise NoteGenerationError("AI service returned an empty response. Please try again.")

    response_text = re.sub(
        r"^```(?:json)?\s*|\s*```$", "", response_text.strip(), flags=re.MULTILINE
    )

    try:
        soap_content = _extract_json_from_response(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"[BEDROCK] Failed to parse response as JSON (length={len(response_text)}): {e}")
        raise NoteGenerationError(f"Failed to parse generated note: {str(e)}")

    return {
        "soap_content": soap_content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        "duration_seconds": duration_seconds,
        "ttft_ms": ttft_ms,
        "streaming_ms": streaming_ms,
        "output_tokens_per_sec": output_tokens_per_sec,
        "stop_reason": stop_reason,
        "invoke_handshake_ms": invoke_handshake_ms,
    }


# ---------------------------------------------------------------------------
# Compact prompt — same JSON schema, fewer style instructions
# ---------------------------------------------------------------------------

_COMPACT_SYSTEM_PROMPT = """\
You are an expert medical documentation assistant for functional/integrative medicine. \
Generate a comprehensive SOAP note and patient summary from a visit transcript.

RULES:
- Only include information explicitly stated in the transcript.
- Never invent clinical details.
- Omit any field where information is absent (no empty strings, nulls, or placeholders).
- Use numerals for dosages/frequencies.
- ROS must be a single string formatted as "System: findings" separated by newlines.
- Respond with ONLY valid JSON matching the requested schema. No markdown, no explanation."""


# ---------------------------------------------------------------------------
# Section-specific prompts for parallel generation
# ---------------------------------------------------------------------------

_SECTION_SYSTEM = """\
You are an expert medical documentation assistant for functional/integrative medicine. \
Extract ONLY the requested section from a visit transcript. \
Only include information explicitly stated. Never invent clinical details. \
Omit any field where information is absent (no empty strings, nulls, or placeholders). \
Respond with ONLY valid JSON matching the requested schema."""

_SECTION_SCHEMAS = {
    "subjective": """\
Extract the SUBJECTIVE section from this transcript. Write a detailed HPI preserving \
chronology, symptoms, severity, and patient-reported observations. Include ROS as a \
single string ("System: findings" per line). Include medications, supplements, allergies, \
social and family history when mentioned.

```json
{
  "subjective": {
    "reason_for_visit": "[omit if not mentioned]",
    "history_of_present_illness": "[detailed narrative]",
    "review_of_systems": "[single string, System: findings per line]",
    "past_medical_history": "[omit if not mentioned]",
    "current_medications": ["[name, dose, frequency]"],
    "current_supplements": ["[name, dose, frequency]"],
    "allergies": ["[allergen and reaction]"],
    "social_history": "[omit if not mentioned]",
    "family_history": "[omit if not mentioned]"
  }
}
```
Respond with ONLY the JSON object.""",

    "objective": """\
Extract the OBJECTIVE section from this transcript. Include vitals, physical exam \
findings, lab results with actual values, imaging, and any patient-provided results.

```json
{
  "objective": {
    "vitals": {
      "blood_pressure": "[omit if not mentioned]",
      "heart_rate": "[omit if not mentioned]",
      "temperature": "[omit if not mentioned]",
      "weight": "[omit if not mentioned]",
      "height": "[omit if not mentioned]",
      "bmi": "[omit if not mentioned]"
    },
    "physical_exam": "[omit if not mentioned]",
    "lab_results": "[omit if not mentioned]"
  }
}
```
Respond with ONLY the JSON object.""",

    "assessment": """\
Extract the ASSESSMENT section from this transcript. Include all diagnoses and a \
problem-based clinical discussion. Only include interpretations the clinician stated.

```json
{
  "assessment": {
    "diagnoses": ["[diagnosis]"],
    "clinical_discussion": [
      {
        "issue": "[clinical issue]",
        "findings": "[supporting details]",
        "interpretation": "[omit if clinician did not state]",
        "plan_summary": "[what was recommended]"
      }
    ],
    "clinical_reasoning": "[omit if not discussed]"
  }
}
```
Respond with ONLY the JSON object.""",

    "plan": """\
Extract the PLAN section from this transcript. Capture every recommendation: \
prescriptions, supplements, labs, imaging, referrals, lifestyle, patient education, \
and follow-up. Include reasons for changes when mentioned.

```json
{
  "plan": {
    "prescriptions": {
      "add": ["[omit if none]"],
      "continue": ["[omit if none]"],
      "discontinue": ["[omit if none]"]
    },
    "supplements": {
      "add": ["[omit if none]"],
      "continue": ["[omit if none]"],
      "discontinue": ["[omit if none]"]
    },
    "lab_orders": ["[test name]"],
    "imaging_or_referrals": ["[imaging or referral]"],
    "lifestyle_recommendations": "[omit if not mentioned]",
    "patient_education": "[omit if not mentioned]",
    "follow_up": "[omit if not mentioned]"
  }
}
```
Respond with ONLY the JSON object.""",

    "patient_summary": """\
Generate a PATIENT-FACING SUMMARY of the plan discussed in this visit. \
Write for the patient, not the provider. Use plain language, short bullets. \
Focus on what the patient should DO next.

```json
{
  "patient_summary": {
    "title": "Your Care Plan",
    "visit_summary": "[1-3 warm sentences summarizing today's visit]",
    "plan_sections": [
      {
        "heading": "[e.g. Medications, Supplements, Labs & Testing]",
        "items": ["[clear patient-facing bullet]"]
      }
    ],
    "watch_for": ["[symptoms or warning signs — omit if none]"],
    "follow_up": ["[follow-up instructions — omit if none]"]
  }
}
```
Respond with ONLY the JSON object.""",
}


def _generate_parallel(transcript: str, additional_context: str = "") -> dict:
    """Generate SOAP sections in parallel via concurrent Bedrock calls."""
    import concurrent.futures

    settings = get_settings()
    bedrock = _get_bedrock_client()
    model_id = settings.bedrock_model_id

    if additional_context and additional_context.strip():
        transcript_block = f"ADDITIONAL CONTEXT:\n{additional_context}\n\nTRANSCRIPT:\n{transcript}"
    else:
        transcript_block = f"TRANSCRIPT:\n{transcript}"

    system_blocks = [{"type": "text", "text": _SECTION_SYSTEM}]
    sections = ["subjective", "objective", "assessment", "plan", "patient_summary"]

    def _call_section(section_name: str) -> tuple[str, dict]:
        user_blocks = [
            {"type": "text", "text": _SECTION_SCHEMAS[section_name]},
            {"type": "text", "text": transcript_block},
        ]
        result = _invoke_bedrock_streaming(
            bedrock, model_id, system_blocks, user_blocks,
            max_tokens=settings.bedrock_max_tokens, temperature=settings.bedrock_temperature,
        )
        return section_name, result

    _wall_start = time.perf_counter()

    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_call_section, s): s for s in sections}
        for future in concurrent.futures.as_completed(futures):
            section_name = futures[future]
            try:
                name, result = future.result()
                results[name] = result
            except Exception as e:
                logger.error(f"[PARALLEL] Section {section_name} failed: {e}")
                results[section_name] = {"soap_content": {}, "error": str(e)}

    wall_seconds = round(time.perf_counter() - _wall_start, 2)

    merged: dict = {}
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    section_timings: dict[str, dict] = {}

    for name, result in results.items():
        content = result.get("soap_content", {})
        if name in content:
            merged[name] = content[name]
        elif name == "patient_summary" and "patient_summary" not in content:
            merged.update(content)
        else:
            merged.update(content)

        total_input += result.get("input_tokens", 0)
        total_output += result.get("output_tokens", 0)
        total_cache_read += result.get("cache_read_input_tokens", 0)
        total_cache_write += result.get("cache_creation_input_tokens", 0)
        section_timings[name] = {
            "duration_s": result.get("duration_seconds"),
            "ttft_ms": result.get("ttft_ms"),
            "streaming_ms": result.get("streaming_ms"),
        }

    subj = merged.get("subjective")
    if isinstance(subj, dict) and isinstance(subj.get("review_of_systems"), dict):
        subj["review_of_systems"] = _normalize_ros(subj["review_of_systems"])
    merged = _normalize_soap_content(merged)

    merged["metadata"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.bedrock_model_id,
        "confidence_score": None,
        "strategy": "parallel",
        "usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_creation_input_tokens": total_cache_write,
            "cache_read_input_tokens": total_cache_read,
        },
        "generation_duration_seconds": wall_seconds,
        "timing": {
            "total_seconds": wall_seconds,
            "section_timings": section_timings,
            "parallel_calls": len(sections),
        },
    }
    return merged


def generate_soap_note(transcript: str, additional_context: str = "") -> dict:
    """
    Generate a SOAP note from a transcript using AWS Bedrock.

    The generation strategy is selected by the SOAP_GENERATION_STRATEGY setting:
      - default:    single Sonnet call with full prompt (production behaviour)
      - fast_model: single call with the configured fast model (Haiku-class)
      - parallel:   concurrent per-section calls, merged into the same format
      - compact:    single Sonnet call with a leaner prompt

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

    strategy = settings.soap_generation_strategy

    if strategy == "parallel":
        return _generate_parallel(transcript, additional_context)

    try:
        _client_init_start = time.perf_counter()
        bedrock = _get_bedrock_client()
        client_init_ms = round((time.perf_counter() - _client_init_start) * 1000, 1)

        # Select model and prompt based on strategy
        if strategy == "fast_model":
            model_id = settings.bedrock_fast_model_id
            sys_prompt = SYSTEM_PROMPT
            schema_prompt = _USER_PROMPT_SCHEMA
        elif strategy == "compact":
            model_id = settings.bedrock_model_id
            sys_prompt = _COMPACT_SYSTEM_PROMPT
            schema_prompt = _USER_PROMPT_SCHEMA
        else:
            model_id = settings.bedrock_model_id
            sys_prompt = SYSTEM_PROMPT
            schema_prompt = _USER_PROMPT_SCHEMA

        if additional_context and additional_context.strip():
            transcript_block = f"ADDITIONAL CONTEXT:\n{additional_context}\n\nTRANSCRIPT:\n{transcript}"
        else:
            transcript_block = f"TRANSCRIPT:\n{transcript}"

        system_blocks = [
            {"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}},
        ]
        user_blocks = [
            {"type": "text", "text": schema_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": transcript_block},
        ]

        logger.info(
            f"[BEDROCK REQUEST] strategy={strategy} model={model_id} "
            f"max_tokens={settings.bedrock_max_tokens} temperature={settings.bedrock_temperature} "
            f"transcript_len={len(transcript)} context_len={len(additional_context or '')}"
        )

        result = _invoke_bedrock_streaming(
            bedrock, model_id, system_blocks, user_blocks,
            max_tokens=settings.bedrock_max_tokens, temperature=settings.bedrock_temperature,
        )
        soap_content = result["soap_content"]
        input_tokens = result["input_tokens"]
        output_tokens = result["output_tokens"]
        cache_creation_input_tokens = result["cache_creation_input_tokens"]
        cache_read_input_tokens = result["cache_read_input_tokens"]
        duration_seconds = result["duration_seconds"]
        ttft_ms = result["ttft_ms"]
        streaming_ms = result["streaming_ms"]
        output_tokens_per_sec = result["output_tokens_per_sec"]
        stop_reason = result["stop_reason"]
        invoke_handshake_ms = result["invoke_handshake_ms"]

        logger.info(
            f"[BEDROCK RESPONSE] input_tokens={input_tokens} output_tokens={output_tokens} "
            f"cache_read={cache_read_input_tokens} cache_write={cache_creation_input_tokens} "
            f"duration_seconds={duration_seconds}"
        )
        logger.info(
            f"[SOAP TIMING] strategy={strategy} total_s={duration_seconds} ttft_ms={ttft_ms} "
            f"streaming_ms={streaming_ms} tok_per_s={output_tokens_per_sec} "
            f"client_init_ms={client_init_ms} invoke_handshake_ms={invoke_handshake_ms} "
            f"input_tokens={input_tokens} output_tokens={output_tokens} "
            f"cache_read={cache_read_input_tokens} cache_write={cache_creation_input_tokens} "
            f"stop_reason={stop_reason} transcript_len={len(transcript)}"
        )

        # Coerce review_of_systems to a string if Bedrock returned a dict
        subj = soap_content.get("subjective")
        if isinstance(subj, dict) and isinstance(subj.get("review_of_systems"), dict):
            subj["review_of_systems"] = _normalize_ros(subj["review_of_systems"])

        # Coerce all array fields to lists (model occasionally returns strings)
        soap_content = _normalize_soap_content(soap_content)

        # Validate that at least one SOAP section is present
        soap_keys = {"subjective", "objective", "assessment", "plan"}
        if not soap_keys.intersection(soap_content.keys()):
            logger.error(f"[BEDROCK] Response has no SOAP sections. Keys={list(soap_content.keys())}")
            raise NoteGenerationError(
                "The transcript did not contain enough clinical content to generate a note. "
                "Please record a visit with clinical details and try again."
            )

        soap_content["metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": model_id,
            "confidence_score": None,
            "strategy": strategy,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens,
            },
            "generation_duration_seconds": duration_seconds,
            "timing": {
                "total_seconds": duration_seconds,
                "ttft_ms": ttft_ms,
                "streaming_ms": streaming_ms,
                "output_tokens_per_sec": output_tokens_per_sec,
                "stop_reason": stop_reason,
                "client_init_ms": client_init_ms,
                "invoke_handshake_ms": invoke_handshake_ms,
            },
        }

        logger.info("SOAP note generated successfully")
        return soap_content

    except NoteGenerationError:
        # Re-raise errors we raised intentionally (e.g. empty stream guard) without
        # wrapping them in the generic handler below.
        raise

    except EventStreamError as e:
        # Must be caught before ClientError — EventStreamError subclasses ClientError
        # in this botocore version, so ordering matters.
        error_code = getattr(e, "code", "Unknown")
        logger.error(f"[BEDROCK STREAM] Stream interrupted: code={error_code} error={str(e)}")
        raise NoteGenerationError("AI service stream interrupted. Please try again.")

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
