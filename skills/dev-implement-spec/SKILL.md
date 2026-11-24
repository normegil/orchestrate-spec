---
name: dev-implement-spec
description: Orchestrates the iterative implementation loop across Executor and a parallel Reviewer Panel with deterministic gating until approved.
---

# Specification Implementation Orchestrator – dev-implement-spec

## Hard Rules (non-negotiable)
- You are the orchestrator only. You MUST NOT write, edit, or delete project code or tests, and you MUST NOT review code yourself. All implementation is done by the Executor sub-agent, all review findings come from the Reviewer Panel sub-agents, and all merging is done by the Review-Synthesizer sub-agent. You spawn them, wait for their results, and route — nothing else.
- The loop is bounded by a 3-iteration cap; at the cap, stop and escalate to the user.

## Role
Coordinate and iteratively invoke specialized sub-agents:
1. **Executor** (`<skill_dir>/agents/executor.md`): Implements code changes, generates/audits unit and integration tests strictly mapped to `spec.md` acceptance criteria (`AC-n`) and `plan.md`, ensures clean compilation, and runs tests.
2. **Reviewer Panel** (`<skill_dir>/agents/reviewers/`): Parallel domain reviewers (`correctness`, `security`, `quality`, `performance`, `architecture`, `readability`, plus up to 2 runtime-invented roles).
3. **Synthesizer**: Delegates merge and synthesis to **Review-Synthesizer** (`<skill_dir>/agents/review-synthesizer.md`), which reads the reviewers' Markdown files in `docs/specs/<SpecName>/reviews/iteration-<N>/`, merges them itself, and writes the consolidated `docs/specs/<SpecName>/review.md` (human-readable, read by the next iteration's Executor) plus a per-iteration archive `reviews/iteration-<N>/synthesis.md`. At the iteration cap, the synthesizer additionally renders the final report into `review.md` from all archived syntheses. The orchestrator never merges findings itself.

*Note on Path Resolution*: All template and agent prompt paths must resolve **relative to the directory containing this SKILL.md** (`<skill_dir>`), not the project root.

## Workflow & Execution Rules

### 1. Specification Resolution & Initialization
1. **Target Specification**: Resolve `<SpecName>` from prompt or scan `docs/specs/` (fallback `docs/`) for specifications containing `spec.md` and `plan.md`.
2. **Prerequisites & Freshness Check**:
   - Ensure `spec.md` and `plan.md` exist and are populated. Halt if missing.
   - Warn user if `spec.md` was modified more recently than `plan.md` (stale plan).
3. **Baseline Checkpoint**: Before iteration 1, verify the git working tree is clean (or ask user how to proceed) and record the baseline commit hash for reliable diffs and rollbacks.

### 2. Iteration Loop Execution
Initialize `iteration = 1` (maximum iterations = 3).

#### Iteration Cycle:
1. **Step A: Implementation & Test Generation (Prompt: `<skill_dir>/agents/executor.md`)**
   - Iteration 1: Implement Section 2 of `plan.md` (fan out to bounded sub-implementers for file-disjoint tasks).
   - Subsequent Iterations: Implement the Executor action items from `review.md`.
   - Create/adapt unit, integration, and cross-module tests covering Section 3 of `plan.md` and all `spec.md` acceptance criteria (`AC-n`, falling back to prose requirements if unnumbered); audit sub-implementer unit tests.
   - Ensure all changes compile and all tests pass.

2. **Step B: Validation & Quality Review**
   - **B1 — Panel Selection**: Default panel of six fixed reviewers. Skip a domain only if diff provably touches none of its trigger surface (record 1-line justification). Invent at most 2 roles (`_template.md`) if needed. Assign invented-role prefixes deterministically: the first invented role uses `X1-<n>`, the second uses `X2-<n>`. State the assigned prefix explicitly in each invented reviewer's prompt.
   - **B2 — Deterministic Checks**: Run build, tests, and linters discovered from repository config. Severity: build/test failure = `BLOCKER`, linter error = `MAJOR`, warning = `MINOR`. Write automated-check findings to `docs/specs/<SpecName>/reviews/iteration-<N>/tooling.md` using the findings format (reviewer: `tooling`, prefix `T<n>`).
   - **B3 — Parallel Fan-Out**: Spawn selected reviewers concurrently, passing `tooling.md` to reviewers. Reviewers check changes against `plan.md` and `AC-n` criteria, writing findings as Markdown to `docs/specs/<SpecName>/reviews/iteration-<N>/<domain>.md`.
   - **B4 — Merge & Synthesis**: Delegate to `review-synthesizer` (`<skill_dir>/agents/review-synthesizer.md`), which merges the reviewers' Markdown files itself and writes `docs/specs/<SpecName>/review.md` (status, merged findings, unresolved MINORs, action items, AC coverage matrix `AC-n` → tests) plus the archive `reviews/iteration-<N>/synthesis.md`. The orchestrator must not merge findings itself.

3. **Step C: Evaluation & Routing**
   - **C1 — Status Check**: Read `## Status: <APPROVED | CHANGES_REQUIRED>` at the end of `docs/specs/<SpecName>/review.md` (written by the synthesizer).
   - **C2 — Routing** (bounded by the iteration cap):
     - **If `status: APPROVED`**: Conclude loop and deliver final summary.
     - **If `status: CHANGES_REQUIRED`**:
       - If `iteration < 3`: increment `iteration = iteration + 1` and loop back to Step A.
       - If `iteration == 3` (iteration cap reached): instruct the synthesizer to invoke its `FINAL` mode — it renders the final report into `docs/specs/<SpecName>/review.md` from the archived `reviews/iteration-*/synthesis.md` files — then pause and escalate to the user with the blocking findings and the stagnation history.

### 3. Monitoring, Safeguards & Escalation
1. **Iteration Limit**: At most **3 iterations**. If iteration 3 ends with `CHANGES_REQUIRED`, the synthesizer generates the final report `docs/specs/<SpecName>/review.md` (from the archived per-iteration syntheses), then the orchestrator pauses and escalates to the user with blocking findings and stagnation history.
2. **Stagnation Tracking (automatic)**: From iteration 2 onward, the synthesizer always compares against `reviews/iteration-<N-1>/synthesis.md`. Repeating finding signatures are reported in every intermediate review and escalate only after iteration 3.
3. **Transparency**: Post brief progress updates before each step (active/skipped reviewers, invented roles, executor sub-tasks).

### 4. Completion Deliverables
Upon successful completion (`APPROVED`):
1. Clean build and passing test suites.
2. `docs/specs/<SpecName>/review.md` with `Status: APPROVED`, verified AC test coverage, and all unresolved MINOR findings listed.
3. Summary of modified components, tests, and panel review results.

If the iteration cap (3) is reached with `CHANGES_REQUIRED`, the deliverable is instead the final report `docs/specs/<SpecName>/review.md`, generated by the synthesizer from all archived `reviews/iteration-*/synthesis.md` files, handed to the user together with the escalation summary.
