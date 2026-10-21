# orchestrate-spec

[![skills.sh](https://skills.sh/b/normegil/orchestrate-spec)](https://skills.sh/normegil/orchestrate-spec)

A suite of [agent skills](https://agentskills.io) implementing a complete spec-driven development lifecycle: from requirements analysis, through implementation planning and an iterative implement/test/review loop, to post-implementation documentation.

## Installation

```bash
npx skills add normegil/orchestrate-spec
```

## Usage

The main entry point is the orchestrator skill. Typical invocations:

```
/dev-orchestrate-spec <MySpec>
/dev-orchestrate-spec <LinkToSpecDefinitionFile>
```

- `<MySpec>`: describe the feature or bug in conversation; the pipeline starts with interactive requirements analysis.
- `<LinkToSpecDefinitionFile>`: point to a file containing your requirements (e.g., meeting notes, a ticket export); the pipeline starts from that content.

Each phase can also be invoked individually with its own skill — see [The skills](#the-skills).

## How it works

`dev-orchestrate-spec` coordinates four specialized skills as a single pipeline. Every skill reads and writes under `docs/specs/<SpecName>/`, and the specification name is locked at the start and passed from phase to phase.

Human validation gates are enforced: `spec.md` (phase 1) and `plan.md` (phase 2) are never written without your explicit approval. The implementation loop is automated across an executor, test-generator, a parallel reviewer panel with scripted static checks, and a deterministic review gate; it runs at most 5 iterations before escalating to you, and stops for guidance if the same review remarks repeat without progress.

### Artifacts

Each specification lives in its own directory:

```
docs/specs/<SpecName>/
├── spec.md     # Requirements and acceptance criteria (phase 1)
├── plan.md     # Fine-grained implementation plan (phase 2)
├── reviews/    # Intermediate per-domain findings (per iteration)
└── review.md   # Final consolidated review report (phase 3)
```

`<SpecName>` follows the convention `<yyyy-MM-dd-HH-mm>-<Bug|Feature>-<ResumeIn2Or3Words>`, where the prefix is the creation date and time (e.g., `2026-10-15-14-30-Feature-User-Management`).

## The skills

| Skill | Role | Writes |
|---|---|---|
| `dev-orchestrate-spec` | Orchestrates the full pipeline end to end | — |
| `dev-analyze` | Clarifies requirements interactively, identifies edge cases, proposes alternatives. Read-only except for the spec file | `docs/specs/<SpecName>/spec.md` |
| `dev-plan-spec-implementation` | Researches the codebase read-only, drafts fine-grained actionable steps with a verification plan | `docs/specs/<SpecName>/plan.md` |
| `dev-implement-spec` | Runs the iterative implement / test / review loop across executor (with optional fan-out to bounded sub-implementers), test-generator (single global QA pass), a parallel reviewer panel, and review-synthesizer (bundled in `skills/dev-implement-spec/agents/`) | code, tests, `docs/specs/<SpecName>/reviews/`, `docs/specs/<SpecName>/review.md` |
| `dev-document-spec` | After approval: enriches in-code docs (public APIs, complex logic, gotchas) and updates project `README.md` and `docs/` | docs, comments |

### Using a phase individually

Each skill can run standalone and will resolve its target specification itself:

```
/dev-analyze <task description or requirements file>
/dev-plan-spec-implementation <SpecName>
/dev-implement-spec <SpecName>
/dev-document-spec <SpecName>
```

If `<SpecName>` is omitted, the skill scans `docs/specs/` for specifications that are ready for its phase (e.g., a spec with no plan yet for the planner) and proposes candidates.

## Guardrails

- **Role separation** — the analyst and planner never touch code; all reviewers and the synthesizer operate read-only on project code; the executor, sub-implementers (bound by the executor's constraints), and test-generator do not alter architecture without review.
- **Confirmation gates** — no `spec.md` or `plan.md` is written without explicit user validation.
- **Bounded automation** — the implementation loop caps at 5 iterations and escalates to the user if changes remain unapproved at the end of iteration 5.
- **Escalation** — unresolved questions, build errors, or review failures unapproved after 5 iterations pause the pipeline and surface actionable context to you.

## License

[GPL-3.0-or-later](https://spdx.org/licenses/GPL-3.0-or-later.html)
