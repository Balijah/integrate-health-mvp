#!/usr/bin/env python3
"""Benchmark and quality-check the SOAP note generation pipeline.

Runs generate_soap_note() against a fixed synthetic transcript and reports
timing breakdown, token usage, and prompt-cache metrics.  Optionally compares
two saved outputs (before/after) for section completeness and key-fact
preservation.

Usage:
    # Single run — prints timing to stdout, saves output to a JSON file
    python benchmarks/bench_soap.py

    # Multiple iterations to estimate variance (first run warms cache)
    python benchmarks/bench_soap.py --iterations 3

    # Quality comparison of two saved runs
    python benchmarks/bench_soap.py --compare baseline.json optimized.json

Environment:
    Requires AWS credentials with Bedrock access (the configured model must be
    reachable).  Uses the same settings as the application — set environment
    variables or a .env file as usual.

    IMPORTANT: The transcript used is fully synthetic / de-identified.  Never
    replace it with real patient data.
"""

import argparse
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

TRANSCRIPT_PATH = os.path.join(SCRIPT_DIR, "synthetic_transcript.txt")

EXPECTED_SECTIONS = {"subjective", "objective", "assessment", "plan"}
EXPECTED_PATIENT_SUMMARY_KEYS = {"title", "visit_summary", "plan_sections"}

KEY_FACTS = [
    ("subjective", "history_of_present_illness", "fatigue"),
    ("subjective", "history_of_present_illness", "hair"),
    ("subjective", "history_of_present_illness", "constipat"),
    ("subjective", "history_of_present_illness", "sleep"),
    ("assessment", "diagnoses", "hashimoto"),
    ("assessment", "diagnoses", "hypothyroid"),
    ("plan", None, "levothyroxine"),
    ("plan", None, "vitamin d"),
    ("plan", None, "iron"),
    ("plan", None, "ultrasound"),
    ("plan", None, "6 week"),
    ("objective", "lab_results", "tsh"),
    ("objective", "lab_results", "tpo"),
]


def _deep_text(obj) -> str:
    """Recursively extract all string content from a nested dict/list."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return " ".join(_deep_text(item) for item in obj)
    if isinstance(obj, dict):
        return " ".join(_deep_text(v) for v in obj.values())
    return str(obj)


def check_quality(soap: dict) -> dict:
    """Return a quality report: section completeness and key-fact hits."""
    present_sections = EXPECTED_SECTIONS.intersection(soap.keys())
    missing_sections = EXPECTED_SECTIONS - present_sections

    has_patient_summary = "patient_summary" in soap
    ps_keys = set()
    if has_patient_summary and isinstance(soap["patient_summary"], dict):
        ps_keys = EXPECTED_PATIENT_SUMMARY_KEYS.intersection(soap["patient_summary"].keys())

    fact_results = []
    for section, field, keyword in KEY_FACTS:
        section_data = soap.get(section, {})
        if field:
            search_text = _deep_text(section_data.get(field, ""))
        else:
            search_text = _deep_text(section_data)
        found = keyword.lower() in search_text.lower()
        fact_results.append({
            "section": section,
            "field": field,
            "keyword": keyword,
            "found": found,
        })

    facts_found = sum(1 for f in fact_results if f["found"])
    return {
        "sections_present": sorted(present_sections),
        "sections_missing": sorted(missing_sections),
        "section_completeness": f"{len(present_sections)}/{len(EXPECTED_SECTIONS)}",
        "has_patient_summary": has_patient_summary,
        "patient_summary_keys": sorted(ps_keys),
        "key_facts_found": f"{facts_found}/{len(KEY_FACTS)}",
        "key_facts_detail": fact_results,
    }


def run_benchmark(transcript: str, iterations: int = 1) -> list[dict]:
    """Run generate_soap_note and return timing + quality for each iteration."""
    from app.services.note_generation import generate_soap_note

    results = []
    for i in range(iterations):
        label = f"Run {i + 1}/{iterations}"
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")

        wall_start = time.perf_counter()
        soap = generate_soap_note(transcript)
        wall_seconds = round(time.perf_counter() - wall_start, 2)

        meta = soap.get("metadata", {})
        usage = meta.get("usage", {})
        timing = meta.get("timing", {})

        quality = check_quality(soap)

        result = {
            "iteration": i + 1,
            "wall_seconds": wall_seconds,
            "timing": timing,
            "usage": usage,
            "quality": quality,
            "soap_output": soap,
        }
        results.append(result)

        print(f"  Wall time:        {wall_seconds}s")
        print(f"  TTFT:             {timing.get('ttft_ms')}ms")
        print(f"  Streaming:        {timing.get('streaming_ms')}ms")
        print(f"  Client init:      {timing.get('client_init_ms')}ms")
        print(f"  Invoke handshake: {timing.get('invoke_handshake_ms')}ms")
        print(f"  Tokens/sec:       {timing.get('output_tokens_per_sec')}")
        print(f"  Input tokens:     {usage.get('input_tokens')}")
        print(f"  Output tokens:    {usage.get('output_tokens')}")
        print(f"  Cache write:      {usage.get('cache_creation_input_tokens', 0)}")
        print(f"  Cache read:       {usage.get('cache_read_input_tokens', 0)}")
        print(f"  Sections:         {quality['section_completeness']}")
        print(f"  Patient summary:  {'yes' if quality['has_patient_summary'] else 'NO'}")
        print(f"  Key facts:        {quality['key_facts_found']}")

    return results


def compare_outputs(path_a: str, path_b: str) -> None:
    """Compare two saved benchmark outputs for quality regression."""
    with open(path_a) as f:
        data_a = json.load(f)
    with open(path_b) as f:
        data_b = json.load(f)

    soap_a = data_a.get("soap_output") or data_a.get("results", [{}])[0].get("soap_output", {})
    soap_b = data_b.get("soap_output") or data_b.get("results", [{}])[0].get("soap_output", {})

    qa = check_quality(soap_a)
    qb = check_quality(soap_b)

    print(f"\n{'=' * 60}")
    print("  Quality Comparison: A (baseline) vs B (optimized)")
    print(f"{'=' * 60}")
    print(f"  Sections    A: {qa['section_completeness']}  B: {qb['section_completeness']}")
    print(f"  Pat.Summary A: {qa['has_patient_summary']}  B: {qb['has_patient_summary']}")
    print(f"  Key facts   A: {qa['key_facts_found']}  B: {qb['key_facts_found']}")

    a_facts = {(f["section"], f["keyword"]): f["found"] for f in qa["key_facts_detail"]}
    b_facts = {(f["section"], f["keyword"]): f["found"] for f in qb["key_facts_detail"]}

    regressions = []
    improvements = []
    for key in a_facts:
        if a_facts[key] and not b_facts.get(key, False):
            regressions.append(key)
        elif not a_facts[key] and b_facts.get(key, False):
            improvements.append(key)

    if regressions:
        print(f"\n  REGRESSIONS ({len(regressions)}):")
        for sec, kw in regressions:
            print(f"    - {sec}: '{kw}' found in A but NOT in B")
    if improvements:
        print(f"\n  Improvements ({len(improvements)}):")
        for sec, kw in improvements:
            print(f"    + {sec}: '{kw}' found in B but not in A")
    if not regressions and not improvements:
        print("\n  No key-fact differences detected.")

    timing_a = data_a.get("timing") or data_a.get("results", [{}])[0].get("timing", {})
    timing_b = data_b.get("timing") or data_b.get("results", [{}])[0].get("timing", {})
    if timing_a and timing_b:
        print("\n  Timing comparison:")
        for key in ("total_seconds", "ttft_ms", "streaming_ms", "client_init_ms"):
            va = timing_a.get(key)
            vb = timing_b.get(key)
            if va is not None and vb is not None:
                delta = round(vb - va, 1)
                pct = round((delta / va) * 100, 1) if va else 0
                sign = "+" if delta > 0 else ""
                print(f"    {key:25s}  A={va:>10}  B={vb:>10}  delta={sign}{delta} ({sign}{pct}%)")


def main():
    parser = argparse.ArgumentParser(description="Benchmark SOAP note generation")
    parser.add_argument("--iterations", type=int, default=1, help="Number of generation runs")
    parser.add_argument("--output", type=str, default=None, help="Save results to JSON file")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "OPTIMIZED"),
                        help="Compare two saved result files")
    args = parser.parse_args()

    if args.compare:
        compare_outputs(args.compare[0], args.compare[1])
        return

    with open(TRANSCRIPT_PATH) as f:
        transcript = f.read()

    print(f"Transcript length: {len(transcript)} chars")
    results = run_benchmark(transcript, iterations=args.iterations)

    out_path = args.output
    if not out_path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(SCRIPT_DIR, f"result_{ts}.json")

    with open(out_path, "w") as f:
        json.dump({"results": results}, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
