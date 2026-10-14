"""Tests for the benchmark quality-check logic and prompt-caching structure.

These tests verify:
1. The quality checker correctly detects section completeness and key facts
2. The Bedrock request body uses structured content blocks for prompt caching
3. Cache metrics flow through to the response metadata
"""

import json
from unittest.mock import MagicMock, patch

from app.services.note_generation import generate_soap_note


COMPLETE_SOAP = {
    "subjective": {
        "reason_for_visit": "Fatigue",
        "history_of_present_illness": (
            "Patient reports progressive fatigue for 6 weeks with hair loss, "
            "dry skin, constipation, and poor sleep quality."
        ),
        "current_medications": [],
        "current_supplements": ["Vitamin D 2000 IU", "Magnesium glycinate 400 mg"],
        "allergies": ["Sulfa drugs — rash"],
        "family_history": "Mother has Hashimoto's thyroiditis on levothyroxine.",
    },
    "objective": {
        "vitals": {"blood_pressure": "118/76", "heart_rate": "72", "weight": "172 lbs"},
        "physical_exam": "Thyroid slightly enlarged and firm. Delayed ankle reflexes.",
        "lab_results": (
            "TSH 8.2 (ref 0.4-4.0), free T4 0.7 (ref 0.8-1.8), "
            "TPO antibodies 342 (ref <35). Ferritin 22, Vitamin D 28."
        ),
    },
    "assessment": {
        "diagnoses": [
            "Hashimoto's thyroiditis with clinical hypothyroidism",
            "Vitamin D insufficiency",
            "Iron deficiency (low ferritin)",
        ],
        "clinical_discussion": [
            {
                "issue": "Hashimoto's thyroiditis",
                "findings": "Elevated TSH, low free T4, strongly positive TPO antibodies.",
                "interpretation": "Autoimmune hypothyroidism consistent with family history.",
                "plan_summary": "Start levothyroxine 50 mcg daily.",
            }
        ],
    },
    "plan": {
        "prescriptions": {"add": ["Levothyroxine 50 mcg daily on empty stomach"]},
        "supplements": {
            "add": ["Iron bisglycinate 25 mg every other day with vitamin C"],
            "continue": ["Magnesium glycinate 400 mg at night"],
        },
        "lab_orders": ["Reverse T3", "Complete iron panel", "Selenium and zinc levels"],
        "imaging_or_referrals": ["Thyroid ultrasound"],
        "lifestyle_recommendations": (
            "Anti-inflammatory diet, reduce gluten, increase water to 64 oz daily, "
            "2 tbsp ground flaxseed daily, 2-3 brazil nuts daily for selenium."
        ),
        "follow_up": "Return in 6 weeks for TSH and free T4 recheck.",
    },
    "patient_summary": {
        "title": "Your Care Plan",
        "visit_summary": "Today we reviewed your fatigue and lab results.",
        "plan_sections": [
            {"heading": "Medications", "items": ["Levothyroxine 50 mcg daily"]},
            {"heading": "Supplements", "items": ["Vitamin D 5000 IU daily", "Iron bisglycinate 25 mg"]},
        ],
        "follow_up": ["Return in 6 weeks"],
    },
}


def _make_stream_events(soap_dict: dict, cache_read: int = 0, cache_write: int = 0):
    """Build mock Bedrock streaming events from a SOAP dict."""
    text = json.dumps(soap_dict)
    usage_fields = {"input_tokens": 2500}
    if cache_read:
        usage_fields["cache_read_input_tokens"] = cache_read
    if cache_write:
        usage_fields["cache_creation_input_tokens"] = cache_write

    events = [
        {"type": "message_start", "message": {"usage": usage_fields}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[:200]}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[200:]}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 800}},
        {"type": "message_stop"},
    ]
    chunks = [{"chunk": {"bytes": json.dumps(ev).encode()}} for ev in events]
    return {"body": iter(chunks)}


class TestQualityChecker:
    """Verify the benchmark quality-check function."""

    def test_complete_soap_passes_all_checks(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "benchmarks"))
        from bench_soap import check_quality

        report = check_quality(COMPLETE_SOAP)
        assert report["section_completeness"] == "4/4"
        assert report["has_patient_summary"] is True
        assert len(report["sections_missing"]) == 0

        facts_found = sum(1 for f in report["key_facts_detail"] if f["found"])
        assert facts_found >= 10, f"Expected >=10 key facts, got {facts_found}"

    def test_missing_section_detected(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "benchmarks"))
        from bench_soap import check_quality

        incomplete = {k: v for k, v in COMPLETE_SOAP.items() if k != "plan"}
        report = check_quality(incomplete)
        assert "plan" in report["sections_missing"]
        assert report["section_completeness"] == "3/4"


class TestPromptCachingStructure:
    """Verify the request body uses structured content blocks for caching."""

    def test_request_uses_content_blocks_with_cache_control(self):
        captured_body = {}

        def capture_invoke(**kwargs):
            captured_body.update(json.loads(kwargs["body"]))
            return _make_stream_events(COMPLETE_SOAP)

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = capture_invoke

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        system = captured_body["system"]
        assert isinstance(system, list), "system should be a list of content blocks"
        assert system[0]["type"] == "text"
        assert system[0]["cache_control"] == {"type": "ephemeral"}

        user_content = captured_body["messages"][0]["content"]
        assert isinstance(user_content, list), "user content should be a list of blocks"
        assert len(user_content) == 2
        assert user_content[0]["cache_control"] == {"type": "ephemeral"}
        assert "TRANSCRIPT:" in user_content[1]["text"]
        assert "cache_control" not in user_content[1]

    def test_cache_metrics_in_metadata(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.return_value = _make_stream_events(
            COMPLETE_SOAP, cache_read=1800, cache_write=0,
        )

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            result = generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        usage = result["metadata"]["usage"]
        assert usage["cache_read_input_tokens"] == 1800
        assert usage["cache_creation_input_tokens"] == 0

    def test_cache_write_metrics_in_metadata(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.return_value = _make_stream_events(
            COMPLETE_SOAP, cache_read=0, cache_write=2300,
        )

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            result = generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        usage = result["metadata"]["usage"]
        assert usage["cache_read_input_tokens"] == 0
        assert usage["cache_creation_input_tokens"] == 2300
