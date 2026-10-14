"""Tests for experimental SOAP generation strategies.

Verifies that each strategy (default, fast_model, compact, parallel) produces
a valid SOAP note, selects the correct model/prompt, and records strategy in
metadata.  All Bedrock calls are mocked.
"""

import json
from unittest.mock import MagicMock, patch

from app.services.note_generation import (
    generate_soap_note,
    _generate_parallel,
    SYSTEM_PROMPT,
    _COMPACT_SYSTEM_PROMPT,
    _USER_PROMPT_SCHEMA,
)


COMPLETE_SOAP = {
    "subjective": {
        "reason_for_visit": "Fatigue",
        "history_of_present_illness": "Fatigue for 6 weeks, hair loss, constipation, poor sleep.",
        "current_medications": [],
        "current_supplements": ["Vitamin D 2000 IU"],
        "allergies": ["Sulfa drugs"],
        "family_history": "Mother has Hashimoto's thyroiditis.",
    },
    "objective": {
        "vitals": {"blood_pressure": "118/76", "heart_rate": "72"},
        "physical_exam": "Thyroid slightly enlarged.",
        "lab_results": "TSH 8.2, TPO antibodies 342.",
    },
    "assessment": {
        "diagnoses": ["Hashimoto's thyroiditis with hypothyroidism"],
        "clinical_discussion": [{"issue": "Hashimoto's", "findings": "Elevated TSH"}],
    },
    "plan": {
        "prescriptions": {"add": ["Levothyroxine 50 mcg daily"]},
        "supplements": {"add": ["Iron bisglycinate 25 mg"]},
        "lab_orders": ["Reverse T3"],
        "imaging_or_referrals": ["Thyroid ultrasound"],
        "follow_up": "Return in 6 weeks.",
    },
    "patient_summary": {
        "title": "Your Care Plan",
        "visit_summary": "We reviewed your fatigue and labs today.",
        "plan_sections": [{"heading": "Medications", "items": ["Levothyroxine 50 mcg"]}],
        "follow_up": ["Return in 6 weeks"],
    },
}


def _make_stream_events(soap_dict: dict):
    text = json.dumps(soap_dict)
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 2000}}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": text}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 500}},
        {"type": "message_stop"},
    ]
    return {"body": iter([{"chunk": {"bytes": json.dumps(e).encode()}} for e in events])}


class TestFastModelStrategy:
    """Verify the fast_model strategy uses the fast model ID."""

    def test_uses_fast_model_id(self):
        captured = {}

        def capture_invoke(**kwargs):
            captured["model"] = kwargs["modelId"]
            captured["body"] = json.loads(kwargs["body"])
            return _make_stream_events(COMPLETE_SOAP)

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = capture_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "fast_model"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_fast_model_id = "us.anthropic.claude-haiku-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                result = generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        assert captured["model"] == "us.anthropic.claude-haiku-4-5-20250929-v1:0"
        assert result["metadata"]["model_version"] == "us.anthropic.claude-haiku-4-5-20250929-v1:0"
        assert result["metadata"]["strategy"] == "fast_model"
        assert "subjective" in result

    def test_uses_full_system_prompt(self):
        captured = {}

        def capture_invoke(**kwargs):
            captured["body"] = json.loads(kwargs["body"])
            return _make_stream_events(COMPLETE_SOAP)

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = capture_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "fast_model"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_fast_model_id = "us.anthropic.claude-haiku-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        system_text = captured["body"]["system"][0]["text"]
        assert system_text == SYSTEM_PROMPT


class TestCompactStrategy:
    """Verify the compact strategy uses the compact system prompt."""

    def test_uses_compact_system_prompt(self):
        captured = {}

        def capture_invoke(**kwargs):
            captured["body"] = json.loads(kwargs["body"])
            return _make_stream_events(COMPLETE_SOAP)

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = capture_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "compact"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                result = generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        system_text = captured["body"]["system"][0]["text"]
        assert system_text == _COMPACT_SYSTEM_PROMPT
        assert len(system_text) < len(SYSTEM_PROMPT)
        assert result["metadata"]["strategy"] == "compact"
        assert result["metadata"]["model_version"] == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def test_uses_same_json_schema(self):
        captured = {}

        def capture_invoke(**kwargs):
            captured["body"] = json.loads(kwargs["body"])
            return _make_stream_events(COMPLETE_SOAP)

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = capture_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "compact"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        user_schema = captured["body"]["messages"][0]["content"][0]["text"]
        assert user_schema == _USER_PROMPT_SCHEMA


class TestParallelStrategy:
    """Verify the parallel strategy makes concurrent calls and merges results."""

    def test_makes_five_concurrent_calls(self):
        call_count = {"n": 0}

        def _mock_invoke(**kwargs):
            call_count["n"] += 1
            body = json.loads(kwargs["body"])
            user_text = body["messages"][0]["content"][0]["text"]
            if "SUBJECTIVE" in user_text:
                return _make_stream_events({"subjective": COMPLETE_SOAP["subjective"]})
            if "OBJECTIVE" in user_text:
                return _make_stream_events({"objective": COMPLETE_SOAP["objective"]})
            if "ASSESSMENT" in user_text:
                return _make_stream_events({"assessment": COMPLETE_SOAP["assessment"]})
            if "PLAN section" in user_text:
                return _make_stream_events({"plan": COMPLETE_SOAP["plan"]})
            if "PATIENT-FACING" in user_text:
                return _make_stream_events({"patient_summary": COMPLETE_SOAP["patient_summary"]})
            return _make_stream_events({})

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = _mock_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "parallel"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                result = _generate_parallel("Doctor: Hello. Patient: I have fatigue.")

        assert call_count["n"] == 5
        assert "subjective" in result
        assert "objective" in result
        assert "assessment" in result
        assert "plan" in result
        assert "patient_summary" in result
        assert result["metadata"]["strategy"] == "parallel"
        assert result["metadata"]["timing"]["parallel_calls"] == 5

    def test_merges_section_timings(self):
        def _mock_invoke(**kwargs):
            return _make_stream_events({"subjective": {"reason_for_visit": "Test"}})

        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.side_effect = _mock_invoke

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "parallel"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                result = _generate_parallel("Doctor: Hello.")

        section_timings = result["metadata"]["timing"]["section_timings"]
        for name in ("subjective", "objective", "assessment", "plan", "patient_summary"):
            assert name in section_timings
            assert "duration_s" in section_timings[name]


class TestDefaultStrategy:
    """Verify default strategy unchanged."""

    def test_default_strategy_records_default(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model_with_response_stream.return_value = _make_stream_events(COMPLETE_SOAP)

        mock_settings = MagicMock()
        mock_settings.soap_generation_strategy = "default"
        mock_settings.bedrock_model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        mock_settings.bedrock_max_tokens = 16384
        mock_settings.bedrock_temperature = 0.3
        mock_settings.aws_region = "us-east-1"

        with patch("app.services.note_generation._get_bedrock_client", return_value=mock_bedrock):
            with patch("app.services.note_generation.get_settings", return_value=mock_settings):
                result = generate_soap_note("Doctor: Hello. Patient: I have fatigue.")

        assert result["metadata"]["strategy"] == "default"
        assert result["metadata"]["model_version"] == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
