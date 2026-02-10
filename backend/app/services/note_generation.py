"""
SOAP Note generation service using Anthropic Claude.

Generates structured SOAP notes from visit transcripts.
"""

import json
import logging
import re
from datetime import datetime, timezone

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


class NoteGenerationError(Exception):
    """Custom exception for note generation failures."""

    pass


# System prompt for functional medicine SOAP note generation
SYSTEM_PROMPT = """You are an expert medical documentation assistant specializing in functional medicine. Your role is to generate comprehensive SOAP notes from patient visit transcripts.

Functional medicine focuses on identifying and addressing root causes of disease through a systems-oriented approach. When generating notes, consider:
- Root cause analysis rather than just symptom management
- Interconnections between body systems
- Lifestyle factors (diet, sleep, stress, exercise)
- Environmental factors and toxin exposure
- Nutritional deficiencies and supplementation
- Gut health and microbiome considerations
- Hormonal balance
- Inflammation markers

Generate structured SOAP notes in the exact JSON format specified. Be thorough but concise. Extract all relevant clinical information from the transcript.

If information is not mentioned in the transcript, use empty strings or empty arrays for those fields - do not make up information.

Important: Your response must be valid JSON only, with no additional text before or after."""

USER_PROMPT_TEMPLATE = """Generate a SOAP note from the following patient visit transcript.

{additional_context}

TRANSCRIPT:
{transcript}

Generate the SOAP note in this exact JSON structure:
{{
  "subjective": {{
    "chief_complaint": "Main reason for visit",
    "history_of_present_illness": "Detailed history of current condition",
    "review_of_systems": "Systems review findings",
    "past_medical_history": "Relevant past medical history",
    "medications": ["List of current medications"],
    "supplements": ["List of current supplements"],
    "allergies": ["Known allergies"],
    "social_history": "Lifestyle factors, occupation, habits",
    "family_history": "Relevant family medical history"
  }},
  "objective": {{
    "vitals": {{
      "blood_pressure": "BP reading if mentioned",
      "heart_rate": "HR if mentioned",
      "temperature": "Temp if mentioned",
      "weight": "Weight if mentioned"
    }},
    "physical_exam": "Physical examination findings",
    "lab_results": "Any lab results discussed"
  }},
  "assessment": {{
    "diagnoses": ["Primary and secondary diagnoses/impressions"],
    "clinical_reasoning": "Clinical reasoning and root cause analysis"
  }},
  "plan": {{
    "treatment_plan": "Overall treatment approach",
    "medications_prescribed": ["New medications prescribed"],
    "supplements_recommended": ["Supplements recommended"],
    "lifestyle_recommendations": "Diet, exercise, sleep, stress management recommendations",
    "lab_orders": ["Labs ordered"],
    "follow_up": "Follow-up plan",
    "patient_education": "Education provided to patient"
  }}
}}

Respond with ONLY the JSON object, no additional text."""


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


def generate_soap_note(transcript: str, additional_context: str | None = None) -> dict:
    """
    Generate a SOAP note from a transcript using Claude.

    Args:
        transcript: The visit transcript text.
        additional_context: Optional additional context (patient history, etc.).

    Returns:
        dict containing the structured SOAP note content.

    Raises:
        NoteGenerationError: If generation fails.
    """
    settings = get_settings()

    if not settings.anthropic_api_key:
        raise NoteGenerationError(
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment."
        )

    if not transcript or not transcript.strip():
        raise NoteGenerationError("Transcript is empty. Cannot generate note.")

    try:
        # Initialize Anthropic client
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        # Build user prompt
        context_section = ""
        if additional_context:
            context_section = f"ADDITIONAL CONTEXT:\n{additional_context}\n\n"

        user_prompt = USER_PROMPT_TEMPLATE.format(
            additional_context=context_section,
            transcript=transcript,
        )

        # Call Claude API
        logger.info("Generating SOAP note with Claude...")
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.3,  # Lower temperature for consistency
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        # Extract response text
        response_text = message.content[0].text

        # Capture token usage from Claude API response
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        logger.info(f"Claude API usage - Input tokens: {input_tokens}, Output tokens: {output_tokens}")

        # Parse JSON response - handle potential markdown code blocks or extra text
        try:
            soap_content = _extract_json_from_response(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON (length={len(response_text)})")
            logger.debug(f"Response content: {response_text[:500]}...")
            raise NoteGenerationError(f"Failed to parse generated note: {str(e)}")

        # Add metadata including token usage
        soap_content["metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "claude-sonnet-4-20250514",
            "confidence_score": None,  # Could be enhanced with confidence estimation
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }

        logger.info("SOAP note generated successfully")
        return soap_content

    except anthropic.APIConnectionError as e:
        logger.error(f"Failed to connect to Anthropic API: {str(e)}")
        raise NoteGenerationError("Failed to connect to AI service. Please try again.")

    except anthropic.RateLimitError as e:
        logger.error(f"Anthropic API rate limit exceeded: {str(e)}")
        raise NoteGenerationError("AI service rate limit exceeded. Please try again later.")

    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error (status={e.status_code})")
        raise NoteGenerationError("AI service error. Please try again.")

    except Exception as e:
        logger.error(f"Unexpected error generating note: {type(e).__name__}")
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
    text = text.replace("- ", "  • ")

    return text


# Cost calculation constants (as of 2024)
# Claude Sonnet pricing
CLAUDE_SONNET_INPUT_COST_PER_MILLION = 3.00  # $3 per 1M input tokens
CLAUDE_SONNET_OUTPUT_COST_PER_MILLION = 15.00  # $15 per 1M output tokens

# Deepgram pricing (nova-2-medical, pay-as-you-go)
DEEPGRAM_COST_PER_MINUTE = 0.0043  # $0.0043 per minute


def calculate_claude_cost(input_tokens: int, output_tokens: int) -> dict:
    """
    Calculate the cost of a Claude API call.

    Args:
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.

    Returns:
        dict with input_cost, output_cost, and total_cost in USD.
    """
    input_cost = (input_tokens / 1_000_000) * CLAUDE_SONNET_INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * CLAUDE_SONNET_OUTPUT_COST_PER_MILLION
    total_cost = input_cost + output_cost

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
    }


def calculate_deepgram_cost(duration_minutes: float) -> dict:
    """
    Calculate the estimated cost of Deepgram transcription.

    Args:
        duration_minutes: Audio duration in minutes.

    Returns:
        dict with duration and cost in USD.
    """
    cost = duration_minutes * DEEPGRAM_COST_PER_MINUTE

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
        input_tokens: Claude input tokens.
        output_tokens: Claude output tokens.
        audio_duration_minutes: Optional audio duration for Deepgram cost.

    Returns:
        dict with detailed cost breakdown.
    """
    claude_costs = calculate_claude_cost(input_tokens, output_tokens)

    result = {
        "claude": claude_costs,
        "deepgram": None,
        "total_cost_usd": claude_costs["total_cost_usd"],
    }

    if audio_duration_minutes is not None:
        deepgram_costs = calculate_deepgram_cost(audio_duration_minutes)
        result["deepgram"] = deepgram_costs
        result["total_cost_usd"] = round(
            claude_costs["total_cost_usd"] + deepgram_costs["cost_usd"], 4
        )

    return result
