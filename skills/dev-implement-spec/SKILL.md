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
4. **Deterministic Gate & Synthesizer**: Executes automated checks, merges findings via `<skill_dir>/scripts/merge-findings.py`, and invokes **Review-Synthesizer** (`<skill_dir>/agents/review-synthesizer.md`) to write `docs/specs/<SpecName>/review.md`.

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
   - **C1 — Panel Selection**: Default panel of six fixed reviewers. Skip a domain only if diff provably touches none of its trigger surface (record 1-line justification). Invent at most 2 roles (`_template.md`, prefix `X1`/`X2`) if needed.
   - **C2 — Deterministic Checks**: Run build, tests, and linters discovered from repository config. Severity: build/test failure = `BLOCKER`, linter error = `MAJOR`, warning = `MINOR`.
   - **C3 — Parallel Fan-Out**: Spawn selected reviewers concurrently. Reviewers check changes against `plan.md` and `AC-n` criteria, writing findings to `docs/specs/<SpecName>/reviews/iteration-<N>/<domain>.md`.
   - **C4 — Merge & Synthesis**:
     - Run: `python <skill_dir>/scripts/merge-findings.py <SpecName> <iteration> [--previous <prev_iteration>]`.
     - Delegate to `review-synthesizer` (`<skill_dir>/agents/review-synthesizer.md`) to write `docs/specs/<SpecName>/review.md` including findings and an AC coverage matrix (`AC-n` → tests).

4. **Step D: Evaluation & Routing**
   - Check `Status: [APPROVED | CHANGES_REQUIRED]` in `review.md`.
   - **If `APPROVED`**: Conclude loop and deliver final summary.
   - **If `CHANGES_REQUIRED`**: Increment `iteration = iteration + 1`. If iteration <= 5, loop back to Step A with action items.

### 3. Monitoring, Safeguards & Escalation
1. **Iteration Limit**: At most **5 iterations**. If iteration 5 ends with `CHANGES_REQUIRED`, pause and escalate to the user with blocking findings and stagnation history.
2. **Stagnation Tracking**: `merge-findings.py` tracks repeating finding signatures across iterations to guide implementers. Stagnation is reported in intermediate reviews and escalates only after iteration 5.
3. **Transparency**: Post brief progress updates before each step (active/skipped reviewers, invented roles, executor sub-tasks).

### 4. Completion Deliverables
Upon successful completion (`APPROVED`):
1. Clean build and passing test suites.
2. `docs/specs/<SpecName>/review.md` with `Status: APPROVED` and verified AC test coverage.
3. Summary of modified components, tests, and panel review results.
