---
name: dev-implement-spec
description: Orchestrates the iterative implementation loop across Executor, Test-Generator, and a parallel Reviewer Panel with deterministic gating until approved.
---

# Specification Implementation Orchestrator – dev-implement-spec

## Role
You are the Orchestration Agent for the specification implementation lifecycle. Your role is to coordinate and iteratively invoke specialized sub-agents:
1. **Executor** (`./agents/executor.md`): Implements code changes, ensures compilation, and runs existing tests.
2. **Test-Generator** (`./agents/test-generator.md`): Generates and adapts unit and integration tests strictly matching `spec.md`, `plan.md`, and implemented code.
3. **Reviewer Panel** (`./agents/reviewers/`): Parallel specialized domain reviewers (`correctness`, `security`, `quality`, `performance`, `architecture`, `readability`, plus up to 2 runtime-invented roles).
4. **Deterministic Gate & Synthesizer**: Runs automated linting, building, and testing checks, merges findings via `scripts/merge-findings.py`, and invokes **Review-Synthesizer** (`./agents/review-synthesizer.md`) to write `docs/specs/<SpecName>/review.md`.

You manage loop transitions, monitor iteration limits, detect repetition, and report progress transparently until a verified solution is delivered.

## Workflow & Execution Rules

### 1. Specification Resolution & Initialization
1. **Target Specification**:
   - Resolve `<SpecName>` from user prompt or scan `docs/specs/` (fallback `docs/`) for directories containing `spec.md` and `plan.md` lacking completed approval.
2. **Prerequisites Check**:
   - Ensure `docs/specs/<SpecName>/spec.md` and `docs/specs/<SpecName>/plan.md` exist and are populated. Halt if missing.

### 2. Iteration Loop Execution
Initialize `iteration = 1` (default maximum iterations = 5).

#### Iteration Cycle:
For each iteration:

1. **Step A: Code Implementation & Compilation (Prompt: `./agents/executor.md`)**
   - Iteration 1: Delegate to `executor` to implement Section 2 of `plan.md`, fanning out to bounded sub-implementers under its Parallelization Rules when tasks are provably independent.
   - Subsequent Iterations: Delegate to `executor` with action items from `review.md` (fanning out to bounded sub-implementers when action items are file-disjoint).
   - The `executor` coordinates implementation, runs integration builds and test suites, and ensures all changes compile cleanly and pass tests. (Sub-implementer fan-out is internal to the executor; the orchestrator never spawns sub-implementers directly).

2. **Step B: Test Generation & Execution (Prompt: `./agents/test-generator.md`)**
   - Iteration 1: Delegate to `test-generator` to create Unit/Integration tests from Section 3 of `plan.md`.
   - Subsequent Iterations: Delegate to `test-generator` if `review.md` identifies test additions or adjustments.
   - The `test-generator` verifies test compilation and passes tests against implemented code.

3. **Step C: Validation & Quality Review**
   - **C1 — Panel Selection**:
     - Default panel: six fixed domain reviewers (`reviewer-correctness.md`, `reviewer-security.md`, `reviewer-quality.md`, `reviewer-performance.md`, `reviewer-architecture.md`, `reviewer-readability.md`).
     - **Skip Rule**: A reviewer may be skipped only if the diff provably touches none of that domain's trigger surface (e.g., no I/O, no user input, no auth → skip security). Record each skip with a 1-line justification in status update.
     - **Invented Roles**: When changes require domain focus outside fixed roles, orchestrator may invent at most 2 roles derived strictly from `./agents/reviewers/_template.md` (prefix `X1`/`X2`, announced in status update).
   - **C2 — Deterministic Checks (Linting, Building & Testing)**:
     - Discover and execute project build, test suites, and configured linters/static analyzers directly from repository config. Never guess commands; record missing tools as unconfigured.
     - Severity mapping for automated tool findings: build/test failure → `BLOCKER` (action: `executor` or `test-generator`), linter/static analyzer error → `MAJOR`, warning → `MINOR`.
   - **C3 — Parallel Fan-Out**:
     - Spawn all selected reviewers concurrently in parallel.
     - Pass `<SpecName>`, `iteration`, and reviewer prompt path (with instructions not to duplicate findings caught by automated linting, building, or testing tools).
     - Each reviewer writes findings to `docs/specs/<SpecName>/reviews/iteration-<N>/<domain>.md`.
   - **C4 — Merge & Synthesis**:
     - Run: `python skills/dev-implement-spec/scripts/merge-findings.py <SpecName> <iteration> [--previous <prev_iteration>]`.
     - If the script fails validation, re-invoke the offending reviewer to fix its findings file.
     - Delegate to `review-synthesizer` (`./agents/review-synthesizer.md`) to write `docs/specs/<SpecName>/review.md` from the script's output.

4. **Step D: Evaluation & Routing**
   - Read `Status: [APPROVED | CHANGES_REQUIRED]` in `docs/specs/<SpecName>/review.md`.
   - **If `APPROVED`**: Implementation complete and verified. Conclude loop and deliver final summary.
   - **If `CHANGES_REQUIRED`**:
     - Increment `iteration = iteration + 1`.
     - Check loop limits. Log stagnation report from merge script for implementer context.
     - Continue to next iteration using action items from `review.md`.

### 3. Monitoring, Safeguards & User Interaction
1. **Iteration Limit & Escalation**: At most **5 iterations**. If iteration 5 finishes with `CHANGES_REQUIRED` (or unresolved stagnation across iterations), pause and escalate to the user with blocking context and stagnation history.
2. **Stagnation Detection**: `merge-findings.py` tracks repeating finding signatures (`file + category + severity`) across consecutive cycles to inform the executor and test-generator. Stagnation is reported in intermediate reviews but does not escalate to the user before the completion of 5 iterations.
3. **Transparency**: Post concise progress updates before each step (announcing active reviewers, skipped roles, invented domains, and executor sub-implementer fan-out with IDs and scopes).

### 4. Completion Deliverables
When the loop finishes successfully:
1. All changes compile and tests pass cleanly.
2. `docs/specs/<SpecName>/review.md` confirms `Status: APPROVED`.
3. Present summary of modified components, tests, and panel review results.
