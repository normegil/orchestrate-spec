#!/usr/bin/env python3
"""
merge-findings.py - Deterministic findings validation, deduplication, gate computation,
and stagnation reporting for the dev-implement-spec review panel.

Ingests the reviewers' JSON files (docs/specs/<SpecName>/reviews/iteration-<N>/*.json)
and prints a single consolidated JSON report to stdout.

Standard library only. Python 3 compatible.
Usage:
    python3 merge-findings.py <SpecName> <iteration> [--previous <iteration_or_tag>]

From iteration 2 onward, --previous defaults to <iteration - 1>.
Exit codes: 0 = report printed, 1 = setup error, 2 = VALIDATION FAILED.
"""

import sys
import json
import re
import argparse
from pathlib import Path

VALID_SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "INFO"}
SEVERITY_ORDER = {"BLOCKER": 4, "MAJOR": 3, "MINOR": 2, "INFO": 1}
VALID_ACTIONS = {"executor", "none"}
REQUIRED_FINDING_FIELDS = ["id", "severity", "file", "line", "category", "title", "detail", "suggested_fix", "action_for"]
DOMAIN_PREFIX_MAP = {
    "correctness": "C",
    "security": "S",
    "quality": "Q",
    "performance": "P",
    "architecture": "A",
    "readability": "R",
    "tooling": "T",
}
# Files written by the synthesizer inside an iteration dir; never ingested as reviewer output.
EXCLUDED_FILES = {"synthesis.json"}


def find_spec_dir(spec_name):
    candidates = [
        Path("docs/specs") / spec_name,
        Path("docs") / spec_name,
        Path(spec_name),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Default to docs/specs/<spec_name>
    return Path("docs/specs") / spec_name


def parse_iteration_number(iter_str):
    m = re.search(r"(\d+)", str(iter_str))
    if m:
        return int(m.group(1))
    return int(iter_str)


def parse_findings_file(file_path):
    """
    Parses one reviewer JSON file.
    Returns (reviewer, summary, findings_list, errors).
    """
    errors = []
    summary = ""
    findings = []

    if not file_path.is_file():
        return file_path.stem, summary, findings, [f"File not found: {file_path}"]

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        return file_path.stem, summary, findings, [f"Cannot parse JSON in {file_path.name}: {e}"]

    if not isinstance(data, dict):
        return file_path.stem, summary, findings, [f"{file_path.name}: top level must be a JSON object"]

    reviewer = data.get("reviewer") or file_path.stem
    summary = str(data.get("summary", "")).strip()
    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        return reviewer, summary, findings, [f"{file_path.name}: 'findings' must be an array"]

    for i, raw in enumerate(raw_findings):
        where = f"{file_path.name} finding #{i + 1}"
        if not isinstance(raw, dict):
            errors.append(f"{where}: must be an object")
            continue
        missing = [f for f in REQUIRED_FINDING_FIELDS if f not in raw or raw[f] in (None, "")]
        if missing:
            errors.append(f"{where}: missing required field(s): {', '.join(missing)}")
            continue

        fid = str(raw["id"]).strip()
        sev = str(raw["severity"]).strip().upper()
        act_for = str(raw["action_for"]).strip().lower()

        if sev not in VALID_SEVERITIES:
            errors.append(f"{where}: invalid severity '{raw['severity']}'. Must be one of {sorted(VALID_SEVERITIES)}")
        if act_for not in VALID_ACTIONS:
            errors.append(f"{where}: invalid action_for '{raw['action_for']}'. Must be one of {sorted(VALID_ACTIONS)}")

        # ID prefix check
        rev_lower = str(reviewer).lower()
        expected_prefix = DOMAIN_PREFIX_MAP.get(rev_lower)
        if expected_prefix:
            if not re.match(rf"^{expected_prefix}\d+$", fid, re.IGNORECASE):
                errors.append(f"{where}: finding ID '{fid}' does not match prefix '{expected_prefix}' for reviewer '{reviewer}' (e.g. {expected_prefix}1)")
        else:
            # Invented role: prefix must be X1- or X2-
            if not re.match(r"^X[12]-\d+$", fid, re.IGNORECASE):
                errors.append(f"{where}: invented reviewer '{reviewer}' finding ID '{fid}' must use prefix X1 or X2 (e.g. X1-1)")

        line_val = raw["line"]
        if not isinstance(line_val, (int, str)):
            errors.append(f"{where}: 'line' must be an integer or a range string like '42-45', got {type(line_val).__name__}")

        findings.append({
            "id": fid,
            "severity": sev if sev in VALID_SEVERITIES else str(raw["severity"]),
            "file": str(raw["file"]).strip(),
            "line": line_val,
            "category": str(raw["category"]).strip(),
            "title": str(raw["title"]).strip(),
            "detail": str(raw["detail"]).strip(),
            "suggested_fix": str(raw["suggested_fix"]).strip(),
            "action_for": act_for if act_for in VALID_ACTIONS else str(raw["action_for"]),
            "reviewer": reviewer,
            "source_file": file_path.name,
        })

    return reviewer, summary, findings, errors


def parse_line_range(line_str):
    """
    Parses line values like 42, '42', '42-45', '42,45' into a set of line integers.
    """
    if isinstance(line_str, int):
        return {line_str}
    if not line_str or str(line_str) in ("–", "-", "N/A"):
        return set()
    nums = set()
    for part in str(line_str).replace(";", ",").split(","):
        part = part.strip()
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start = int(bounds[0].strip())
                end = int(bounds[1].strip())
                nums.update(range(min(start, end), max(start, end) + 1))
            except ValueError:
                pass
        else:
            try:
                nums.add(int(part))
            except ValueError:
                pass
    return nums


def deduplicate_findings(findings):
    """
    Deduplicates findings based on same file, same category, and actually
    overlapping line ranges. Keeps the highest severity.

    A finding without line information never overlaps: distinct defects in
    the same file and category must survive.
    """
    merged = []
    discarded = []

    for item in findings:
        item_lines = parse_line_range(item["line"])
        item_cat = item["category"].strip().lower()
        item_file = item["file"].strip().lower()

        dup_idx = -1
        for i, existing in enumerate(merged):
            ext_file = existing["file"].strip().lower()
            ext_cat = existing["category"].strip().lower()
            if item_file and item_file == ext_file and item_cat and item_cat == ext_cat:
                ext_lines = parse_line_range(existing["line"])
                overlap = bool(item_lines) and bool(ext_lines) and not item_lines.isdisjoint(ext_lines)
                if overlap:
                    dup_idx = i
                    break

        if dup_idx >= 0:
            existing = merged[dup_idx]
            existing_sev_val = SEVERITY_ORDER.get(existing["severity"], 0)
            item_sev_val = SEVERITY_ORDER.get(item["severity"], 0)
            if item_sev_val > existing_sev_val:
                discarded.append({"id": existing["id"], "severity": existing["severity"], "file": existing["file"], "line": existing["line"], "category": existing["category"], "reason": f"merged with {item['reviewer']}-{item['id']}"})
                merged[dup_idx] = item
            else:
                discarded.append({"id": item["id"], "severity": item["severity"], "file": item["file"], "line": item["line"], "category": item["category"], "reason": f"merged with {existing['reviewer']}-{existing['id']}"})
        else:
            merged.append(item)

    return merged, discarded


def check_stagnation(curr_findings, prev_findings):
    """
    Finds findings with identical signature (file + category + severity) in both iterations.
    """
    stagnant = []
    prev_sigs = {}
    for f in prev_findings:
        sig = (f["file"].strip().lower(), f["category"].strip().lower(), f["severity"].upper())
        prev_sigs[sig] = f

    for f in curr_findings:
        sig = (f["file"].strip().lower(), f["category"].strip().lower(), f["severity"].upper())
        if sig in prev_sigs:
            stagnant.append({
                "current_id": f["id"],
                "previous_id": prev_sigs[sig]["id"],
                "severity": f["severity"],
                "file": f["file"],
                "line": f["line"],
                "category": f["category"],
            })
    return stagnant


def load_iteration_findings(iter_dir):
    """
    Loads and validates all reviewer JSON files in an iteration directory.
    Returns (panel_summary, all_findings, errors_dict).
    """
    panel_summary = []
    all_findings = []
    all_errors = {}
    seen_ids = set()

    finding_files = sorted(p for p in iter_dir.glob("*.json") if p.name not in EXCLUDED_FILES)
    for fpath in finding_files:
        reviewer, summary, findings, errors = parse_findings_file(fpath)

        for f in findings:
            fid = f["id"]
            if fid in seen_ids:
                errors.append(f"Duplicate finding ID '{fid}' across review files")
            else:
                seen_ids.add(fid)

        if errors:
            all_errors[fpath.name] = errors

        blockers = sum(1 for f in findings if f["severity"] == "BLOCKER")
        majors = sum(1 for f in findings if f["severity"] == "MAJOR")
        all_findings.extend(findings)
        panel_summary.append({
            "reviewer": reviewer,
            "file": fpath.name,
            "summary": summary,
            "blockers": blockers,
            "majors": majors,
            "findings": findings,
        })

    return panel_summary, all_findings, all_errors


def main():
    parser = argparse.ArgumentParser(description="Merge and gate review findings (JSON in, JSON out).")
    parser.add_argument("spec_name", help="Specification name (directory name under docs/specs/)")
    parser.add_argument("iteration", help="Iteration number or tag (e.g. 1, iteration-1)")
    parser.add_argument("--previous", help="Previous iteration number or tag to detect stagnation (e.g. 1, iteration-1). Defaults to <iteration - 1> from iteration 2 onward.")
    args = parser.parse_args()

    spec_dir = find_spec_dir(args.spec_name)
    iter_num = parse_iteration_number(args.iteration)
    iter_dir = spec_dir / "reviews" / f"iteration-{iter_num}"

    if not iter_dir.is_dir():
        sys.stderr.write(f"ERROR: Findings directory not found: {iter_dir}\n")
        sys.exit(1)

    finding_files = [p for p in iter_dir.glob("*.json") if p.name not in EXCLUDED_FILES]
    if not finding_files:
        sys.stderr.write(f"ERROR: No reviewer JSON files found in {iter_dir}\n")
        sys.exit(1)

    panel_summary, all_findings, all_errors = load_iteration_findings(iter_dir)

    if all_errors:
        sys.stderr.write("VALIDATION FAILED:\n")
        for fname, errs in all_errors.items():
            sys.stderr.write(f"  [{fname}]\n")
            for e in errs:
                sys.stderr.write(f"    - {e}\n")
        sys.exit(2)

    # Deduplicate findings
    merged_findings, discarded = deduplicate_findings(all_findings)

    # Compute verdict
    counts = {sev: sum(1 for f in merged_findings if f["severity"] == sev) for sev in ["BLOCKER", "MAJOR", "MINOR", "INFO"]}
    verdict = "APPROVED" if (counts["BLOCKER"] == 0 and counts["MAJOR"] == 0) else "CHANGES_REQUIRED"

    # Action items grouped
    executor_actions = [f for f in merged_findings if f["action_for"] == "executor"]

    # Stagnation. From iteration 2 onward, always compare against the previous
    # iteration (--previous defaults to iteration - 1).
    prev_tag = args.previous
    if prev_tag is None and iter_num >= 2:
        prev_tag = str(iter_num - 1)

    stagnation = None
    if prev_tag:
        prev_iter_num = parse_iteration_number(prev_tag)
        prev_iter_dir = spec_dir / "reviews" / f"iteration-{prev_iter_num}"
        if prev_iter_dir.is_dir():
            _, prev_all_findings, prev_errors = load_iteration_findings(prev_iter_dir)
            if not prev_errors:
                prev_merged, _ = deduplicate_findings(prev_all_findings)
                stagnant = check_stagnation(merged_findings, prev_merged)
                stagnation = {
                    "previous_iteration": prev_iter_num,
                    "repeating_count": len(stagnant),
                    "repeating": stagnant,
                }
            else:
                sys.stderr.write(f"WARNING: previous iteration findings failed validation, stagnation skipped: {prev_iter_dir}\n")
        else:
            sys.stderr.write(f"WARNING: Stagnation analysis skipped: previous iteration directory not found: {prev_iter_dir}\n")

    report = {
        "spec": args.spec_name,
        "iteration": iter_num,
        "status": verdict,
        "counts": counts,
        "panel": [
            {
                "reviewer": p["reviewer"],
                "file": p["file"],
                "summary": p["summary"],
                "blockers": p["blockers"],
                "majors": p["majors"],
                "status": "APPROVED" if (p["blockers"] == 0 and p["majors"] == 0) else "CHANGES_REQUIRED",
                "findings": p["findings"],
            }
            for p in panel_summary
        ],
        "findings": merged_findings,
        "deduplicated": discarded,
        "stagnation": stagnation,
        "unresolved_minors": [f for f in merged_findings if f["severity"] == "MINOR"],
        "action_items": {
            "executor": executor_actions,
        },
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
