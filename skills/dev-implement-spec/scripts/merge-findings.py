#!/usr/bin/env python3
"""
merge-findings.py - Deterministic findings validation, deduplication, gate computation,
and stagnation reporting for the dev-implement-spec review panel.

Standard library only. Python 3 compatible.
Usage:
    python merge-findings.py <SpecName> <iteration> [--previous <iteration_or_tag>]
"""

import sys
import os
import re
import argparse
from pathlib import Path

VALID_SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "INFO"}
SEVERITY_ORDER = {"BLOCKER": 4, "MAJOR": 3, "MINOR": 2, "INFO": 1}
VALID_ACTIONS = {"executor", "test-generator", "none"}
DOMAIN_PREFIX_MAP = {
    "correctness": "C",
    "security": "S",
    "quality": "Q",
    "performance": "P",
    "architecture": "A",
    "readability": "R",
    "tooling": "T",
}


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
    m = re.search(r"(\d+)", iter_str)
    if m:
        return int(m.group(1))
    return int(iter_str)


def parse_findings_file(file_path):
    """
    Parses a findings markdown file.
    Returns (metadata, findings_list, verdict_counts, remarks, errors).
    """
    errors = []
    metadata = {}
    findings = []
    verdict_counts = {"blockers": 0, "majors": 0}
    remarks = ""

    if not file_path.is_file():
        errors.append(f"File not found: {file_path}")
        return metadata, findings, verdict_counts, remarks, errors

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"Cannot read {file_path}: {e}")
        return metadata, findings, verdict_counts, remarks, errors

    # 1. Parse frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not fm_match:
        errors.append("Missing or malformed YAML frontmatter (must start and end with ---)")
        body = content
    else:
        fm_text = fm_match.group(1)
        body = content[fm_match.end():]
        for line in fm_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                    metadata[k] = items
                elif v:
                    metadata[k] = v.strip("'\"")
                else:
                    metadata[k] = []
            elif line.startswith("- ") and "files_reviewed" in metadata and isinstance(metadata["files_reviewed"], list):
                metadata["files_reviewed"].append(line[2:].strip().strip("'\""))

    reviewer = metadata.get("reviewer")
    if not reviewer:
        errors.append("Frontmatter missing required 'reviewer' field")

    # 2. Parse table
    # Expected table columns: ID | Severity | File | Line | Category | Description | Action for | Suggested action
    table_lines = []
    in_table = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            parts = [p.strip() for p in s.split("|")[1:-1]]
            if len(parts) >= 8:
                if "ID" in parts[0] and "Severity" in parts[1]:
                    in_table = True
                    continue
                if in_table:
                    if all(re.match(r"^:?-+:?$", p) for p in parts):
                        continue  # separator line
                    table_lines.append(parts)
        elif in_table and s and not s.startswith("|"):
            in_table = False

    # 3. Parse Domain verdict section
    blocker_m = re.search(r"-\s*blockers\s*:\s*(\d+)", body, re.IGNORECASE)
    major_m = re.search(r"-\s*majors\s*:\s*(\d+)", body, re.IGNORECASE)
    remarks_m = re.search(r"-\s*remarks\s*:\s*(.+)", body, re.IGNORECASE)

    if blocker_m:
        verdict_counts["blockers"] = int(blocker_m.group(1))
    else:
        errors.append("Domain verdict missing '- blockers: <count>'")

    if major_m:
        verdict_counts["majors"] = int(major_m.group(1))
    else:
        errors.append("Domain verdict missing '- majors: <count>'")

    if remarks_m:
        remarks = remarks_m.group(1).strip()
    else:
        # Check if remarks are under a heading or multi-line
        r_sec = re.search(r"##\s*Domain verdict.*?\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
        if r_sec:
            rem_lines = [l.strip() for l in r_sec.group(1).splitlines() if l.strip() and not l.strip().startswith("- blockers") and not l.strip().startswith("- majors")]
            if rem_lines:
                remarks = " ".join(rem_lines).lstrip("- remarks:").strip()

    # 4. Validate findings rows
    actual_blockers = 0
    actual_majors = 0

    for row in table_lines:
        fid, sev, fpath, line_no, cat, desc, act_for, sug_act = [x.strip() for x in row[:8]]
        
        # Check for empty findings row
        if (fid in ("–", "-", "N/A", "none") or not fid) and ("no findings" in desc.lower() or "no findings" in cat.lower() or sev in ("–", "-", "NONE", "N/A")):
            continue

        sev_upper = sev.upper()
        if sev_upper not in VALID_SEVERITIES:
            errors.append(f"Invalid severity '{sev}' in finding {fid}. Must be one of {VALID_SEVERITIES}")
        else:
            if sev_upper == "BLOCKER":
                actual_blockers += 1
            elif sev_upper == "MAJOR":
                actual_majors += 1

        act_for_lower = act_for.lower()
        if act_for_lower not in VALID_ACTIONS:
            errors.append(f"Invalid 'Action for' '{act_for}' in finding {fid}. Must be one of {VALID_ACTIONS}")

        # ID prefix check
        if reviewer:
            rev_lower = str(reviewer).lower()
            expected_prefix = DOMAIN_PREFIX_MAP.get(rev_lower)
            if expected_prefix:
                if not re.match(rf"^{expected_prefix}\d+$", fid, re.IGNORECASE):
                    errors.append(f"Finding ID '{fid}' does not match prefix '{expected_prefix}' for reviewer '{reviewer}' (e.g. {expected_prefix}1)")
            else:
                # Invented role: prefix should be X1 or X2
                if not re.match(r"^X[12]-\d+$", fid, re.IGNORECASE) and not re.match(r"^X[12]\d+$", fid, re.IGNORECASE):
                    errors.append(f"Invented reviewer '{reviewer}' finding ID '{fid}' must use prefix X1 or X2 (e.g. X1-1 or X11)")

        findings.append({
            "id": fid,
            "severity": sev_upper,
            "file": fpath,
            "line": line_no,
            "category": cat,
            "description": desc,
            "action_for": act_for_lower,
            "suggested_action": sug_act,
            "reviewer": reviewer or "unknown",
            "source_file": file_path.name
        })

    # Validate declared vs actual counts
    if blocker_m and verdict_counts["blockers"] != actual_blockers:
        errors.append(f"Declared blockers ({verdict_counts['blockers']}) does not match table count ({actual_blockers})")
    if major_m and verdict_counts["majors"] != actual_majors:
        errors.append(f"Declared majors ({verdict_counts['majors']}) does not match table count ({actual_majors})")

    return metadata, findings, verdict_counts, remarks, errors


def parse_line_range(line_str):
    """
    Parses line strings like '42', '42-45', '42,45', '–' into a set of line integers.
    """
    if not line_str or line_str in ("–", "-", "N/A"):
        return set()
    nums = set()
    for part in line_str.replace(";", ",").split(","):
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
    Deduplicates findings based on same file, overlapping line range, and same category.
    Keeps the highest severity.
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
                # Check line overlap or both have no lines
                overlap = False
                if item_lines and ext_lines:
                    if not item_lines.isdisjoint(ext_lines):
                        overlap = True
                elif not item_lines and not ext_lines:
                    overlap = True
                elif not item_lines or not ext_lines:
                    # One has no lines, but same file & category
                    overlap = True
                
                if overlap:
                    dup_idx = i
                    break

        if dup_idx >= 0:
            existing = merged[dup_idx]
            existing_sev_val = SEVERITY_ORDER.get(existing["severity"], 0)
            item_sev_val = SEVERITY_ORDER.get(item["severity"], 0)
            if item_sev_val > existing_sev_val:
                # Replace with higher severity finding
                discarded.append((existing, f"merged with {item['reviewer']}-{item['id']}"))
                merged[dup_idx] = item
            else:
                discarded.append((item, f"merged with {existing['reviewer']}-{existing['id']}"))
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
            stagnant.append((f, prev_sigs[sig]))
    return stagnant


def main():
    parser = argparse.ArgumentParser(description="Merge and gate review findings.")
    parser.add_argument("spec_name", help="Specification name (directory name under docs/specs/)")
    parser.add_argument("iteration", help="Iteration number or tag (e.g. 1, iteration-1)")
    parser.add_argument("--previous", help="Previous iteration number or tag to detect stagnation (e.g. 1, iteration-1)")
    args = parser.parse_args()

    spec_dir = find_spec_dir(args.spec_name)
    iter_num = parse_iteration_number(args.iteration)
    iter_dir = spec_dir / "reviews" / f"iteration-{iter_num}"

    if not iter_dir.is_dir():
        sys.stderr.write(f"ERROR: Findings directory not found: {iter_dir}\n")
        sys.exit(1)

    finding_files = sorted(list(iter_dir.glob("*.md")))
    if not finding_files:
        sys.stderr.write(f"ERROR: No findings markdown files found in {iter_dir}\n")
        sys.exit(1)

    all_errors = {}
    all_findings = []
    panel_summary = []
    seen_ids = set()

    for fpath in finding_files:
        meta, findings, v_counts, remarks, errors = parse_findings_file(fpath)
        reviewer = meta.get("reviewer", fpath.stem)
        
        # Check ID uniqueness across panel
        for f in findings:
            fid = f["id"]
            if fid in seen_ids:
                errors.append(f"Duplicate finding ID '{fid}' across review files")
            else:
                seen_ids.add(fid)

        if errors:
            all_errors[fpath.name] = errors

        all_findings.extend(findings)
        panel_summary.append({
            "reviewer": reviewer,
            "file": fpath.name,
            "blockers": v_counts["blockers"],
            "majors": v_counts["majors"],
            "findings_count": len(findings),
            "remarks": remarks
        })

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
    total_blockers = sum(1 for f in merged_findings if f["severity"] == "BLOCKER")
    total_majors = sum(1 for f in merged_findings if f["severity"] == "MAJOR")
    total_minors = sum(1 for f in merged_findings if f["severity"] == "MINOR")
    total_infos = sum(1 for f in merged_findings if f["severity"] == "INFO")

    verdict = "APPROVED" if (total_blockers == 0 and total_majors == 0) else "CHANGES_REQUIRED"

    # Action items grouped
    executor_actions = [f for f in merged_findings if f["action_for"] == "executor"]
    testgen_actions = [f for f in merged_findings if f["action_for"] == "test-generator"]

    # Check stagnation if previous iteration provided
    stagnant_findings = []
    if args.previous:
        prev_iter_num = parse_iteration_number(args.previous)
        prev_iter_dir = spec_dir / "reviews" / f"iteration-{prev_iter_num}"
        if prev_iter_dir.is_dir():
            prev_all_findings = []
            for pf in sorted(list(prev_iter_dir.glob("*.md"))):
                _, p_finds, _, _, p_errs = parse_findings_file(pf)
                if not p_errs:
                    prev_all_findings.extend(p_finds)
            prev_merged, _ = deduplicate_findings(prev_all_findings)
            stagnant_findings = check_stagnation(merged_findings, prev_merged)

    # Output formatting to stdout
    print(f"# Review Merge Report - {args.spec_name}")
    print(f"Iteration: {iter_num}")
    print(f"Status: {verdict}")
    print(f"Blockers: {total_blockers} | Majors: {total_majors} | Minors: {total_minors} | Info: {total_infos}\n")

    print("## Panel Summary")
    for p in panel_summary:
        rev_verdict = "APPROVED" if (p["blockers"] == 0 and p["majors"] == 0) else "CHANGES_REQUIRED"
        print(f"- **{p['reviewer']}** (`{p['file']}`): {p['blockers']} blockers, {p['majors']} majors | Status: {rev_verdict}")
        if p["remarks"]:
            print(f"  Remarks: {p['remarks']}")
    print()

    print("## Consolidated Findings")
    if not merged_findings:
        print("| ID | Severity | File | Line | Category | Description | Action for | Suggested action |")
        print("|---|---|---|---|---|---|---|---|")
        print("| – | – | – | – | – | No findings across review panel | none | – |")
    else:
        print("| ID | Severity | File | Line | Category | Description | Action for | Suggested action |")
        print("|---|---|---|---|---|---|---|---|")
        for f in merged_findings:
            print(f"| {f['id']} | {f['severity']} | {f['file']} | {f['line']} | {f['category']} | {f['description']} | {f['action_for']} | {f['suggested_action']} |")
    print()

    if discarded:
        print("## Deduplicated Items")
        for d, reason in discarded:
            print(f"- Finding {d['id']} ({d['severity']}) on `{d['file']}:{d['line']}` ({d['category']}): {reason}")
        print()

    if args.previous:
        print("## Stagnation Report")
        if stagnant_findings:
            print(f"WARNING: {len(stagnant_findings)} repeating findings detected across iteration {args.previous} and {iter_num}:")
            for curr_f, prev_f in stagnant_findings:
                print(f"- Repeating {curr_f['severity']} [{curr_f['category']}] on `{curr_f['file']}:{curr_f['line']}` (Current ID: {curr_f['id']}, Prev ID: {prev_f['id']})")
        else:
            print("No stagnant findings detected from previous iteration.")
        print()

    print("## Action Items & Next Steps")
    print("### Executor Tasks")
    if executor_actions:
        for f in executor_actions:
            print(f"- [{f['id']} - {f['severity']}] `{f['file']}:{f['line']}`: {f['description']} -> Action: {f['suggested_action']}")
    else:
        print("- No pending action items for Executor.")
    print()

    print("### Test-Generator Tasks")
    if testgen_actions:
        for f in testgen_actions:
            print(f"- [{f['id']} - {f['severity']}] `{f['file']}:{f['line']}`: {f['description']} -> Action: {f['suggested_action']}")
    else:
        print("- No pending action items for Test-Generator.")
    print()

    print(f"## Status: {verdict}")


if __name__ == "__main__":
    main()
