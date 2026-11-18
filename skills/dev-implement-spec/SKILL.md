---
name: dev-implement-spec
description: Orchestrates the iterative implementation loop across Executor and a parallel Reviewer Panel with deterministic gating until approved.
---

# Specification Implementation Orchestrator – dev-implement-spec

## Hard Rules (non-negotiable)
- You are the orchestrator only. You MUST NOT write, edit, or delete project code or tests, and you MUST NOT review code yourself. All implementation is done by the Executor sub-agent, all review findings come from the Reviewer Panel sub-agents, and all merging is done by the Review-Synthesizer sub-agent. You spawn them, wait for their results, and route — nothing else.
- The deterministic gate in Step C is mandatory and checks the filesystem, not your judgment. It is bounded by the same 3-iteration cap as the loop itself; at the cap, stop and escalate to the user. Never loop on the gate outside the iteration structure.

## Role
Coordinate and iteratively invoke specialized sub-agents:
1. **Executor** (`<skill_dir>/agents/executor.md`): Implements code changes, generates/audits unit and integration tests strictly mapped to `spec.md` acceptance criteria (`AC-n`) and `plan.md`, ensures clean compilation, and runs tests.
2. **Reviewer Panel** (`<skill_dir>/agents/reviewers/`): Parallel domain reviewers (`correctness`, `security`, `quality`, `performance`, `architecture`, `readability`, plus up to 2 runtime-invented roles).
3. **Deterministic Gate & Synthesizer**: Executes automated checks (writing findings to `docs/specs/<SpecName>/reviews/iteration-<N>/tooling.json`), then delegates merge and synthesis to **Review-Synthesizer** (`<skill_dir>/agents/review-synthesizer.md`), which executes `<skill_dir>/scripts/merge-findings.py` over the reviewers' JSON files and writes the consolidated `docs/specs/<SpecName>/review.json` (machine-readable, ingested by the next iteration's Executor) plus a per-iteration archive `reviews/iteration-<N>/synthesis.json`. At the iteration cap, the synthesizer additionally renders the final human-readable `docs/specs/<SpecName>/review.md`. The orchestrator never runs the merge script itself.

*Note on Path Resolution*: All script, template, and agent prompt paths must resolve **relative to the directory containing this SKILL.md** (`<skill_dir>`), not the project root.

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
   - Subsequent Iterations: Implement `action_items.executor` from `review.json`.
   - Create/adapt unit, integration, and cross-module tests covering Section 3 of `plan.md` and all `spec.md` acceptance criteria (`AC-n`, falling back to prose requirements if unnumbered); audit sub-implementer unit tests.
   - Ensure all changes compile and all tests pass.

2. **Step B: Validation & Quality Review**
   - **B1 — Panel Selection**: Default panel of six fixed reviewers. Skip a domain only if diff provably touches none of its trigger surface (record 1-line justification). Invent at most 2 roles (`_template.md`) if needed. Assign invented-role prefixes deterministically: the first invented role uses `X1-<n>`, the second uses `X2-<n>`. State the assigned prefix explicitly in each invented reviewer's prompt.
   - **B2 — Deterministic Checks**: Run build, tests, and linters discovered from repository config. Severity: build/test failure = `BLOCKER`, linter error = `MAJOR`, warning = `MINOR`. Write automated-check findings to `docs/specs/<SpecName>/reviews/iteration-<N>/tooling.json` using the JSON findings format (reviewer: `tooling`, prefix `T<n>`).
   - **B3 — Parallel Fan-Out**: Spawn selected reviewers concurrently, passing `tooling.json` to reviewers. Reviewers check changes against `plan.md` and `AC-n` criteria, writing findings as JSON to `docs/specs/<SpecName>/reviews/iteration-<N>/<domain>.json`.
   - **B4 — Merge & Synthesis**:
     - Delegate to `review-synthesizer` (`<skill_dir>/agents/review-synthesizer.md`), the sole owner of `merge-findings.py` execution: it runs the script over the reviewers' JSON files and writes `docs/specs/<SpecName>/review.json` (status, merged findings, unresolved MINORs, action items, AC coverage matrix `AC-n` → tests) plus the archive `reviews/iteration-<N>/synthesis.json`. The orchestrator must not run the script or merge findings itself.
     - From iteration 2 onward, instruct the synthesizer to pass `--previous <iteration - 1>` so stagnation analysis is never skipped (iteration 1 has no previous iteration).
     - If the script aborts with `VALIDATION FAILED` (e.g. duplicate finding IDs across invented reviewers), recovery is deterministic: instruct the offending reviewer to renumber its findings using its assigned prefix, then have the synthesizer re-run the script.

3. **Step C: Evaluation & Routing**
   - **C1 — Deterministic Gate (mandatory, first action of Step C)**: Run `python3 <skill_dir>/scripts/check-gate.py <SpecName> --iteration <N>`. This checks the filesystem, not your judgment: it verifies `reviews/iteration-<N>/` contains `tooling.json`, all panel reviewer JSONs, and `synthesis.json`, and that `review.json` exists with a valid `status`. A non-zero exit means the iteration is incomplete (a sub-agent was skipped or its artifact is missing).
   - **C2 — Routing** (applies to both gate failure and `CHANGES_REQUIRED`, bounded by the same iteration cap):
     - **If gate passes and `status: APPROVED`**: Conclude loop and deliver final summary.
     - **If gate fails or `status: CHANGES_REQUIRED`**:
       - If `iteration < 3`: increment `iteration = iteration + 1` and loop back to Step A (on gate failure, the action items must include re-spawning the sub-agent responsible for the missing artifact).
       - If `iteration == 3` (iteration cap reached): instruct the synthesizer to invoke its `FINAL` mode — it renders `docs/specs/<SpecName>/review.md` for the user from the archived `reviews/iteration-*/synthesis.json` files — then pause and escalate to the user with the blocking findings, the gate error output if applicable, and the stagnation history.

### 3. Monitoring, Safeguards & Escalation
1. **Iteration Limit**: At most **3 iterations**. If iteration 3 ends with `CHANGES_REQUIRED` or a failed gate, the synthesizer generates the final markdown report `docs/specs/<SpecName>/review.md` (from the archived per-iteration syntheses), then the orchestrator pauses and escalates to the user with blocking findings, gate output if applicable, and stagnation history.
2. **Stagnation Tracking (automatic)**: From iteration 2 onward, stagnation analysis always runs: the synthesizer passes `--previous <N-1>`, and `merge-findings.py` itself defaults to iteration N-1 when `--previous` is omitted. Repeating finding signatures are reported in every intermediate review and escalate only after iteration 3.
3. **Transparency**: Post brief progress updates before each step (active/skipped reviewers, invented roles, executor sub-tasks).

### 4. Completion Deliverables
Upon successful completion (`APPROVED`):
0. Run `python3 <skill_dir>/scripts/check-gate.py <SpecName> --expect-approved`; it must exit 0 before you deliver the final summary. On failure, resume the loop (bounded by the 3-iteration cap) or escalate — never declare completion on a failed gate.
1. Clean build and passing test suites.
2. `docs/specs/<SpecName>/review.json` with `status: "APPROVED"`, verified AC test coverage, and all unresolved MINOR findings listed.
3. Summary of modified components, tests, and panel review results.

If the iteration cap (3) is reached with `CHANGES_REQUIRED`, the deliverable is instead the final markdown report `docs/specs/<SpecName>/review.md`, generated by the synthesizer from all archived `reviews/iteration-*/synthesis.json` files, handed to the user together with the escalation summary.
