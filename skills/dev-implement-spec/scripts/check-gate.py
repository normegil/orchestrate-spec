#!/usr/bin/env python3
"""
check-gate.py - Deterministic artifact gate for the dev-implement-spec review loop.

Verifies that the per-iteration review artifacts and the consolidated review.json
actually exist on disk before the orchestrator is allowed to route (Step C) or
declare completion. Replaces agent judgment about "did the reviewers run?" with a
pure filesystem check.

Standard library only. Python 3 compatible.
Usage:
    python3 check-gate.py <SpecName> [--iteration N] [--expect-approved]

Checks performed:
    - spec directory resolves (docs/specs/<SpecName>/, docs/<SpecName>/, or <SpecName>/)
    - if --iteration N: reviews/iteration-<N>/ exists and contains tooling.json,
      all six panel reviewer files, and synthesis.json, each parsing as JSON
    - review.json exists, parses, and has status in {APPROVED, CHANGES_REQUIRED}
    - with --expect-approved: status must be APPROVED

Exit codes: 0 = gate passed, 1 = gate failed (first problem printed to stderr).
"""

import sys
import json
import argparse
from pathlib import Path

VALID_STATUSES = {"APPROVED", "CHANGES_REQUIRED"}
PANEL_DOMAINS = ["correctness", "security", "quality", "performance", "architecture", "readability"]


def fail(message):
    print(f"GATE FAILED: {message}", file=sys.stderr)
    sys.exit(1)


def find_spec_dir(spec_name):
    candidates = [
        Path("docs/specs") / spec_name,
        Path("docs") / spec_name,
        Path(spec_name),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    fail(f"spec directory not found for '{spec_name}' (looked in docs/specs/, docs/, ./)")


def check_json_file(path, what):
    if not path.is_file():
        fail(f"missing {what}: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        fail(f"invalid JSON in {what}: {path} ({e})")


def main():
    parser = argparse.ArgumentParser(description="Deterministic artifact gate for dev-implement-spec.")
    parser.add_argument("spec_name", help="Specification name (<SpecName>)")
    parser.add_argument("--iteration", type=int, default=None, help="Iteration number whose artifacts must exist")
    parser.add_argument("--expect-approved", action="store_true", help="Require review.json status == APPROVED")
    args = parser.parse_args()

    spec_dir = find_spec_dir(args.spec_name)

    if args.iteration is not None:
        iteration_dir = spec_dir / "reviews" / f"iteration-{args.iteration}"
        if not iteration_dir.is_dir():
            fail(f"missing iteration directory: {iteration_dir}")
        check_json_file(iteration_dir / "tooling.json", "deterministic tooling findings")
        for domain in PANEL_DOMAINS:
            check_json_file(iteration_dir / f"{domain}.json", f"reviewer findings ({domain})")
        check_json_file(iteration_dir / "synthesis.json", "review-synthesizer archive")

    review_json = spec_dir / "review.json"
    if not review_json.is_file():
        fail(f"missing consolidated review: {review_json}")
    try:
        with open(review_json, "r", encoding="utf-8") as f:
            review = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        fail(f"invalid JSON in consolidated review: {review_json} ({e})")
    status = review.get("status")
    if status not in VALID_STATUSES:
        fail(f"review.json has missing/invalid status (expected one of {sorted(VALID_STATUSES)}, got {status!r}): {review_json}")
    if args.expect_approved and status != "APPROVED":
        fail(f"review.json status is {status}, expected APPROVED: {review_json}")

    print("GATE OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
