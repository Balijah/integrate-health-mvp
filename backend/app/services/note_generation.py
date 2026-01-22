"""
SOAP Note generation service using Anthropic Claude.

Generates structured SOAP notes from visit transcripts.
"""

import json
import logging
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

        # Parse JSON response
        try:
            soap_content = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {response_text[:500]}")
            raise NoteGenerationError(f"Failed to parse generated note: {str(e)}")

        # Add metadata
        soap_content["metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "claude-sonnet-4-20250514",
            "confidence_score": None,  # Could be enhanced with confidence estimation
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
        logger.error(f"Anthropic API error: {str(e)}")
        raise NoteGenerationError(f"AI service error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error generating note: {str(e)}")
        raise NoteGenerationError(f"Failed to generate note: {str(e)}")


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
