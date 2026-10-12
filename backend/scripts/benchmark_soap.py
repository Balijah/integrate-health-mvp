"""Measure model-only latency; never connects to the app database or queue.

Requires an explicitly selected development AWS profile, region and model.
Use synthetic transcripts. Each repeat incurs a Bedrock inference charge.
The existing service preserves one response for SOAP plus patient summary.
"""

import argparse
import importlib.util
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings

_spec = importlib.util.spec_from_file_location(
    "note_generation", Path(__file__).resolve().parents[1] / "app/services/note_generation.py"
)
assert _spec and _spec.loader
note_generation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(note_generation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--profile", required=True, help="Confirmed development AWS profile")
    parser.add_argument("--region", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    transcript = args.transcript.read_text()
    if not transcript.strip() or args.repeat < 1:
        parser.error("Provide a nonempty transcript and a positive repeat count")

    # Explicit settings bypass .env; no database, SQS, S3 or transcription calls.
    settings = Settings(
        _env_file=None,
        environment="development",
        aws_region=args.region,
        bedrock_model_id=args.model,
        bedrock_max_tokens=16384,
        bedrock_temperature=0.3,
    )
    import boto3
    from botocore.config import Config

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    # Keep baseline client creation per run, matching the current service.
    def client():
        return session.client(
            "bedrock-runtime",
            config=Config(read_timeout=600, connect_timeout=10, retries={"max_attempts": 1}),
        )

    # Benchmark output contains timing/token metadata only.
    logging.disable(logging.CRITICAL)
    elapsed = []
    failures = 0
    with patch.object(note_generation, "get_settings", return_value=settings), patch.object(
        note_generation, "_get_bedrock_client", side_effect=client
    ):
        for run in range(1, args.repeat + 1):
            start = time.perf_counter()
            try:
                note = note_generation.generate_soap_note(transcript)
                seconds = round(time.perf_counter() - start, 3)
                elapsed.append(seconds)
                metadata = note["metadata"]
                print(json.dumps({
                    "run": run, "wall_seconds": seconds,
                    "model": metadata["model_version"],
                    "transcript_chars": len(transcript),
                    "timing": metadata["timing"], "usage": metadata["usage"],
                    "sections_present": [key for key in (
                        "subjective", "objective", "assessment", "plan", "patient_summary"
                    ) if note.get(key)],
                }), flush=True)
            except note_generation.NoteGenerationError:
                failures += 1
                print(json.dumps({"run": run, "failed": True,
                                  "wall_seconds": round(time.perf_counter() - start, 3)}), flush=True)
    print(json.dumps({"successful_runs": len(elapsed), "failed_runs": failures,
                      "median_wall_seconds": statistics.median(elapsed) if elapsed else None}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
