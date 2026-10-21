# orchestrate-spec

[![skills.sh](https://skills.sh/b/normegil/orchestrate-spec)](https://skills.sh/normegil/orchestrate-spec)

A suite of [agent skills](https://agentskills.io) implementing a spec-driven development lifecycle: interactive requirements grilling, architectural planning, an iterative implement/test/review loop, and documentation.

## Installation

```bash
npx skills add normegil/orchestrate-spec
```

## Usage

The main entry point is the orchestrator skill:

```
/dev-orchestrate-spec <SpecName>
/dev-orchestrate-spec <LinkToRequirementsFile>
```

- `<MySpec>`: Describe a task in conversation; starts Phase 1 requirements grilling.
- `<LinkToRequirementsFile>`: Point to a requirements file; starts Phase 1 from loaded content.
- `<SpecName>`: Can be one of 2 things, depending on the presence of expected files:
  - Describe a task in conversation; starts Phase 1 requirements grilling.
  - Resume an existing specification pipeline from its detected phase.

Each phase can also run standalone — see [The skills](#the-skills).

## How it works

`dev-orchestrate-spec` coordinates specialized skills across standard phases under `docs/specs/<SpecName>/`:

1. **Requirements Grilling (`dev-analyze`)**: Models requirements as a design tree and asks batched question rounds with recommended answers while discovering repository facts read-only. Grilling ends when the decision frontier is empty.
2. **Implementation Planning (`dev-plan-spec-implementation`)**: Researches codebase context read-only, generates fine-grained tasks, and maps all acceptance criteria (`AC-n`) to tests.
3. **Implementation Loop (`dev-implement-spec`)**: Automated loop coordinating executor, test-generator, and parallel reviewer panel with deterministic gating. Runs at most 5 iterations; tracks stagnation across cycles and escalates only after iteration 5.
4. **Documentation (`dev-document-spec`)**: Enriches in-code documentation and project reference guides.

### Validation Gates & Invalidation

- **Gates**: `spec.md` (Phase 1) and `plan.md` (Phase 2) are never written without explicit user confirmation.
- **Invalidation**: Updating `spec.md` after `plan.md` is written invalidates the plan (re-runs Phase 2). Updating `plan.md` during or after Phase 3 re-runs Phase 3.

### Artifacts

```
docs/specs/<SpecName>/
├── spec.md     # Requirements, testable Acceptance Criteria (AC-n), and Decision Log
├── plan.md     # Fine-grained implementation steps and AC test verification plan
├── reviews/    # Intermediate per-domain findings (per iteration)
└── review.md   # Final review report and AC coverage matrix (Phase 3)
```

`<SpecName>` format: `<yyyy-MM-dd-HH-mm>-<Bug|Feature>-<ResumeIn2Or3Words>` (e.g., `2026-10-15-14-30-Feature-User-Management`).

## The skills

| Skill | Role | Output |
|---|---|---|
| `dev-orchestrate-spec` | Orchestrates lifecycle end-to-end (intake, resume, invalidation) | — |
| `dev-analyze` | Interactive grilling rounds over design tree; records spec | `docs/specs/<SpecName>/spec.md` |
| `dev-plan-spec-implementation` | Read-only codebase research, AC test mapping, and plan review | `docs/specs/<SpecName>/plan.md` |
| `dev-implement-spec` | Iterative executor/test-gen/reviewer loop with deterministic gate | Code, tests, reviews, `review.md` |
| `dev-document-spec` | Post-approval in-code and system documentation | In-code docs, `README.md`, `docs/` |

### Standalone Invocations

```
/dev-analyze <task description or requirements file>
/dev-plan-spec-implementation <SpecName>
/dev-implement-spec <SpecName>
/dev-document-spec <SpecName>
```

If `<SpecName>` is omitted, the skill scans `docs/specs/` and proposes matching specifications ready for that phase.

## Guardrails

- **Role separation**: Analyst and planner do not modify code; reviewers operate strictly read-only; executor and test-generator adhere strictly to `spec.md` and `plan.md`.
- **Explicit validation**: No `spec.md` or `plan.md` is saved without human approval.
- **Bounded execution**: Implementation loop caps at 5 iterations before human escalation.

## Citations & Acknowledgments

The interactive grilling procedure is adapted from Matt Pocock's [grilling skill](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling), which is licensed under the [MIT License](https://spdx.org/licenses/MIT.html) (GPL-3.0-compatible). The upstream notice is reproduced in [NOTICE](NOTICE).

## License

[GPL-3.0-or-later](https://spdx.org/licenses/GPL-3.0-or-later.html) — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
