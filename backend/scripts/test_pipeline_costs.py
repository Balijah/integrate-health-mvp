#!/usr/bin/env python3
"""
SOAP Pipeline Cost Testing Utility

Test API costs for the full SOAP workflow using a plain text transcript
without requiring a real recording.

Usage:
    python scripts/test_pipeline_costs.py /path/to/transcript.txt --duration 90
    python scripts/test_pipeline_costs.py /path/to/transcript.txt --dry-run
"""

import argparse
import os
import sys
from pathlib import Path

# Add the backend app to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    # dotenv not installed - environment variables must be set externally
    pass

from app.services.note_generation import (
    generate_soap_note,
    calculate_claude_cost,
    calculate_deepgram_cost,
    estimate_total_visit_cost,
    NoteGenerationError,
    CLAUDE_SONNET_INPUT_COST_PER_MILLION,
    CLAUDE_SONNET_OUTPUT_COST_PER_MILLION,
    DEEPGRAM_COST_PER_MINUTE,
)


def estimate_tokens_from_text(text: str) -> int:
    """
    Estimate token count from text.

    Rough approximation: ~4 characters per token for English text.
    This is a conservative estimate.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    # Claude tokenizer is similar to GPT: ~4 chars per token on average
    return len(text) // 4


def analyze_transcript(transcript: str) -> dict:
    """
    Analyze transcript statistics.

    Args:
        transcript: The transcript text.

    Returns:
        dict with transcript statistics.
    """
    words = transcript.split()
    characters = len(transcript)
    lines = transcript.count('\n') + 1

    # Estimate speaking duration: average speaking rate is ~150 words/minute
    estimated_duration_minutes = len(words) / 150

    return {
        "word_count": len(words),
        "character_count": characters,
        "line_count": lines,
        "estimated_tokens": estimate_tokens_from_text(transcript),
        "estimated_duration_minutes": round(estimated_duration_minutes, 1),
    }


def print_separator(char: str = "=", length: int = 50) -> None:
    """Print a separator line."""
    print(char * length)


def print_cost_analysis(
    transcript_stats: dict,
    claude_costs: dict | None = None,
    deepgram_costs: dict | None = None,
    is_dry_run: bool = False,
) -> None:
    """
    Print formatted cost analysis.

    Args:
        transcript_stats: Transcript analysis results.
        claude_costs: Claude API cost breakdown (None for dry-run estimates).
        deepgram_costs: Deepgram cost breakdown.
        is_dry_run: Whether this is a dry-run (estimated) analysis.
    """
    print()
    print_separator()
    print("  SOAP Pipeline Cost Analysis")
    if is_dry_run:
        print("  (DRY RUN - Estimated costs)")
    print_separator()
    print()

    # Transcript stats
    print("Transcript Statistics:")
    print(f"  Word count:              {transcript_stats['word_count']:,}")
    print(f"  Character count:         {transcript_stats['character_count']:,}")
    print(f"  Line count:              {transcript_stats['line_count']:,}")
    print(f"  Estimated tokens:        {transcript_stats['estimated_tokens']:,}")
    print(f"  Est. audio duration:     {transcript_stats['estimated_duration_minutes']} minutes")
    print()

    # Deepgram costs
    if deepgram_costs:
        print("Deepgram Transcription (estimated):")
        print(f"  Duration:                {deepgram_costs['duration_minutes']} minutes")
        print(f"  Rate:                    ${DEEPGRAM_COST_PER_MINUTE}/minute")
        print(f"  Cost:                    ${deepgram_costs['cost_usd']:.4f}")
        print()

    # Claude costs
    if claude_costs:
        cost_type = "estimated" if is_dry_run else "actual"
        print(f"Claude SOAP Generation ({cost_type}):")
        print(f"  Input tokens:            {claude_costs['input_tokens']:,}")
        print(f"  Output tokens:           {claude_costs['output_tokens']:,}")
        print(f"  Input cost:              ${claude_costs['input_cost_usd']:.6f}")
        print(f"  Output cost:             ${claude_costs['output_cost_usd']:.6f}")
        print(f"  Total Claude cost:       ${claude_costs['total_cost_usd']:.4f}")
        print()

    # Total
    total_cost = 0.0
    if deepgram_costs:
        total_cost += deepgram_costs['cost_usd']
    if claude_costs:
        total_cost += claude_costs['total_cost_usd']

    print_separator("-")
    print(f"TOTAL ESTIMATED COST PER VISIT: ${total_cost:.4f}")
    print_separator("-")
    print()

    # Pricing reference
    print("Pricing Reference:")
    print(f"  Claude Sonnet Input:     ${CLAUDE_SONNET_INPUT_COST_PER_MILLION}/1M tokens")
    print(f"  Claude Sonnet Output:    ${CLAUDE_SONNET_OUTPUT_COST_PER_MILLION}/1M tokens")
    print(f"  Deepgram nova-2-medical: ${DEEPGRAM_COST_PER_MINUTE}/minute")
    print()


def run_dry_run(transcript: str, duration_minutes: float | None) -> None:
    """
    Run a dry-run cost estimate without calling the API.

    Args:
        transcript: The transcript text.
        duration_minutes: Audio duration in minutes (optional).
    """
    stats = analyze_transcript(transcript)

    # Use provided duration or estimate from transcript
    audio_duration = duration_minutes or stats['estimated_duration_minutes']

    # Estimate Claude tokens
    # Input = system prompt (~500 tokens) + user prompt template (~200 tokens) + transcript
    estimated_input_tokens = 700 + stats['estimated_tokens']
    # Output typically ranges from 1500-2500 tokens for a SOAP note
    estimated_output_tokens = 2000

    claude_costs = calculate_claude_cost(estimated_input_tokens, estimated_output_tokens)
    deepgram_costs = calculate_deepgram_cost(audio_duration)

    print_cost_analysis(
        transcript_stats=stats,
        claude_costs=claude_costs,
        deepgram_costs=deepgram_costs,
        is_dry_run=True,
    )


def run_actual_test(transcript: str, duration_minutes: float | None, additional_context: str | None = None) -> dict | None:
    """
    Run an actual API call to get real token usage.

    Args:
        transcript: The transcript text.
        duration_minutes: Audio duration in minutes (optional).
        additional_context: Optional additional context for note generation.

    Returns:
        Generated SOAP note content dict, or None on failure.
    """
    stats = analyze_transcript(transcript)

    # Use provided duration or estimate from transcript
    audio_duration = duration_minutes or stats['estimated_duration_minutes']

    print("\nGenerating SOAP note via Claude API...")
    print("(This will incur actual API costs)")
    print()

    try:
        result = generate_soap_note(transcript, additional_context)

        # Extract usage from metadata
        usage = result.get("metadata", {}).get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        if not input_tokens or not output_tokens:
            print("Warning: Could not extract token usage from response")
            return result

        claude_costs = calculate_claude_cost(input_tokens, output_tokens)
        deepgram_costs = calculate_deepgram_cost(audio_duration)

        print_cost_analysis(
            transcript_stats=stats,
            claude_costs=claude_costs,
            deepgram_costs=deepgram_costs,
            is_dry_run=False,
        )

        return result

    except NoteGenerationError as e:
        print(f"\nError generating note: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Test API costs for the SOAP pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run actual API call with transcript file
  python scripts/test_pipeline_costs.py transcript.txt

  # Specify audio duration for accurate Deepgram cost estimate
  python scripts/test_pipeline_costs.py transcript.txt --duration 90

  # Dry-run: estimate costs without calling API
  python scripts/test_pipeline_costs.py transcript.txt --dry-run

  # Add additional context for SOAP generation
  python scripts/test_pipeline_costs.py transcript.txt --context "Patient has history of Hashimoto's"
        """
    )

    parser.add_argument(
        "transcript_file",
        type=str,
        help="Path to the transcript text file"
    )

    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=None,
        help="Audio duration in minutes (for Deepgram cost estimate)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate costs without calling APIs"
    )

    parser.add_argument(
        "--context", "-c",
        type=str,
        default=None,
        help="Additional context for SOAP note generation"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save generated SOAP note to file (JSON format)"
    )

    args = parser.parse_args()

    # Read transcript file
    transcript_path = Path(args.transcript_file)
    if not transcript_path.exists():
        print(f"Error: Transcript file not found: {transcript_path}")
        sys.exit(1)

    transcript = transcript_path.read_text(encoding="utf-8")

    if not transcript.strip():
        print("Error: Transcript file is empty")
        sys.exit(1)

    print(f"Loaded transcript: {transcript_path}")
    print(f"File size: {len(transcript):,} bytes")

    if args.dry_run:
        run_dry_run(transcript, args.duration)
    else:
        # Check for API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("\nError: ANTHROPIC_API_KEY environment variable not set")
            print("Set it in your .env file or environment, or use --dry-run for estimates")
            sys.exit(1)

        result = run_actual_test(transcript, args.duration, args.context)

        # Optionally save output
        if result and args.output:
            import json
            output_path = Path(args.output)
            output_path.write_text(json.dumps(result, indent=2))
            print(f"SOAP note saved to: {output_path}")


if __name__ == "__main__":
    main()
