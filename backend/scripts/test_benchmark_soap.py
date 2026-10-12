"""Offline check: python -m unittest discover -s scripts -p test_benchmark_soap.py."""

import contextlib
import io
import json
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark_soap


class BenchmarkCheck(unittest.TestCase):
    def test_reports_timings_and_failures_without_note_text(self):
        service = benchmark_soap.note_generation
        result = {
            "subjective": {"history_of_present_illness": "DO NOT PRINT NOTE TEXT"},
            "metadata": {
                "model_version": "test-model", "timing": {"ttft_ms": 100},
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }
        argv = ["benchmark_soap", str(Path(__file__).with_name("soap_synthetic.txt")),
                "--profile", "offline-test", "--region", "us-east-1",
                "--model", "test-model", "--repeat", "2"]
        output = io.StringIO()
        previous_logging = logging.root.manager.disable
        try:
            with patch("sys.argv", argv), patch("boto3.Session") as session, patch.object(
                service, "generate_soap_note",
                side_effect=[result, service.NoteGenerationError("DO NOT PRINT ERROR TEXT")],
            ), contextlib.redirect_stdout(output):
                self.assertEqual(benchmark_soap.main(), 1)
                session.assert_called_once_with(profile_name="offline-test", region_name="us-east-1")
                session.return_value.client.assert_not_called()
        finally:
            logging.disable(previous_logging)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows[0]["timing"], {"ttft_ms": 100})
        self.assertTrue(rows[1]["failed"])
        self.assertEqual(rows[2]["successful_runs"], 1)
        self.assertEqual(rows[2]["failed_runs"], 1)
        self.assertNotIn("DO NOT PRINT", output.getvalue())
