---
name: dev-implement-spec
description: Orchestrates the iterative implementation loop across Executor, Test-Generator, and a parallel Reviewer Panel with deterministic gating until approved.
---

# Specification Implementation Orchestrator – dev-implement-spec

## Role
Coordinate and iteratively invoke specialized sub-agents:
1. **Executor** (`<skill_dir>/agents/executor.md`): Implements code changes, ensures clean compilation, and runs tests.
2. **Test-Generator** (`<skill_dir>/agents/test-generator.md`): Generates unit and integration tests strictly mapped to `spec.md` acceptance criteria (`AC-n`) and `plan.md`.
3. **Reviewer Panel** (`<skill_dir>/agents/reviewers/`): Parallel domain reviewers (`correctness`, `security`, `quality`, `performance`, `architecture`, `readability`, plus up to 2 runtime-invented roles).
4. **Deterministic Gate & Synthesizer**: Executes automated checks (writing findings to `docs/specs/<SpecName>/reviews/iteration-<N>/tooling.md`), then delegates merge and synthesis to **Review-Synthesizer** (`<skill_dir>/agents/review-synthesizer.md`), which executes `<skill_dir>/scripts/merge-findings.py` and writes `docs/specs/<SpecName>/review.md`. The orchestrator never runs the merge script itself.

*Note on Path Resolution*: All script, template, and agent prompt paths must resolve **relative to the directory containing this SKILL.md** (`<skill_dir>`), not the project root.

## Workflow & Execution Rules

### 1. Specification Resolution & Initialization
1. **Target Specification**: Resolve `<SpecName>` from prompt or scan `docs/specs/` (fallback `docs/`) for specifications containing `spec.md` and `plan.md`.
2. **Prerequisites & Freshness Check**:
   - Ensure `spec.md` and `plan.md` exist and are populated. Halt if missing.
   - Warn user if `spec.md` was modified more recently than `plan.md` (stale plan).
3. **Baseline Checkpoint**: Before iteration 1, verify the git working tree is clean (or ask user how to proceed) and record the baseline commit hash for reliable diffs and rollbacks.

### 2. Iteration Loop Execution
Initialize `iteration = 1` (maximum iterations = 5).

#### Iteration Cycle:
1. **Step A: Code Implementation (Prompt: `<skill_dir>/agents/executor.md`)**
   - Iteration 1: Implement Section 2 of `plan.md` (fan out to bounded sub-implementers for file-disjoint tasks).
   - Subsequent Iterations: Implement action items from `review.md`.
   - Ensure all changes compile and pass existing test suites.

2. **Step B: Test Generation & Traceability (Prompt: `<skill_dir>/agents/test-generator.md`)**
   - Create/adapt unit and integration tests covering Section 3 of `plan.md` and all `spec.md` acceptance criteria (`AC-n`, falling back to prose requirements if unnumbered).
   - Ensure tests compile and pass against implemented code.

3. **Step C: Validation & Quality Review**
   - **C1 — Panel Selection**: Default panel of six fixed reviewers. Skip a domain only if diff provably touches none of its trigger surface (record 1-line justification). Invent at most 2 roles (`_template.md`) if needed. Assign invented-role prefixes deterministically: the first invented role uses `X1-<n>`, the second uses `X2-<n>`. State the assigned prefix explicitly in each invented reviewer's prompt.
   - **C2 — Deterministic Checks**: Run build, tests, and linters discovered from repository config. Severity: build/test failure = `BLOCKER`, linter error = `MAJOR`, warning = `MINOR`. Write automated-check findings to `docs/specs/<SpecName>/reviews/iteration-<N>/tooling.md` using the findings format (reviewer: `tooling`, prefix `T<n>`).
   - **C3 — Parallel Fan-Out**: Spawn selected reviewers concurrently, passing `tooling.md` to reviewers. Reviewers check changes against `plan.md` and `AC-n` criteria, writing findings to `docs/specs/<SpecName>/reviews/iteration-<N>/<domain>.md`.
   - **C4 — Merge & Synthesis**:
     - Delegate to `review-synthesizer` (`<skill_dir>/agents/review-synthesizer.md`), the sole owner of `merge-findings.py` execution: it runs the script and writes `docs/specs/<SpecName>/review.md` including findings, unresolved MINORs, and an AC coverage matrix (`AC-n` → tests). The orchestrator must not run the script or merge findings itself.
     - From iteration 2 onward, instruct the synthesizer to pass `--previous <iteration - 1>` so stagnation analysis is never skipped (iteration 1 has no previous iteration).
     - If the script aborts with `VALIDATION FAILED` (e.g. duplicate finding IDs across invented reviewers), recovery is deterministic: instruct the offending reviewer to renumber its findings using its assigned prefix, then have the synthesizer re-run the script.

4. **Step D: Evaluation & Routing**
   - Check `Status: [APPROVED | CHANGES_REQUIRED]` in `review.md`.
   - **If `APPROVED`**: Conclude loop and deliver final summary.
   - **If `CHANGES_REQUIRED`**: Increment `iteration = iteration + 1`. If iteration <= 5, loop back to Step A with action items.

### 3. Monitoring, Safeguards & Escalation
1. **Iteration Limit**: At most **5 iterations**. If iteration 5 ends with `CHANGES_REQUIRED`, pause and escalate to the user with blocking findings and stagnation history.
2. **Stagnation Tracking (automatic)**: From iteration 2 onward, stagnation analysis always runs: the synthesizer passes `--previous <N-1>`, and `merge-findings.py` itself defaults to iteration N-1 when `--previous` is omitted. Repeating finding signatures are reported in every intermediate review and escalate only after iteration 5.
3. **Transparency**: Post brief progress updates before each step (active/skipped reviewers, invented roles, executor sub-tasks).

### 4. Completion Deliverables
Upon successful completion (`APPROVED`):
1. Clean build and passing test suites.
2. `docs/specs/<SpecName>/review.md` with `Status: APPROVED`, verified AC test coverage, and all unresolved MINOR findings listed.
3. Summary of modified components, tests, and panel review results.
