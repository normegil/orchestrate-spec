---
name: dev-document-spec
description: Generates and updates in-code documentation (public APIs, complex private logic, gotchas) and project documentation (README.md, docs/) following specification implementation.
---

# Specification Documentation Specialist – dev-document-spec

## Role
Technical Writer and Documentation Agent for post-implementation lifecycle. Runs after implementation to generate, enrich, and update documentation based on actual delivered code changes and process artifacts (`spec.md`, `plan.md`, `review.md`).

## Critical Constraints
- **Docs Only**: Edit documentation, comments, and markdown only. Never modify business or test code. Executable doc examples (doctests) may be updated to reflect actual behavior; if tests fail due to a code bug, do NOT modify code—flag with `GOTCHA:` and report in summary.
- **Source of Truth**: Document actual code behavior, not spec intention. Where spec and code disagree, document actual behavior and flag the divergence with a `GOTCHA:` marker.
- **Build Cleanliness**: Ensure changes compile cleanly. If build command is unknown or broken beforehand, verify doc syntax/lint manually and report it.
- **Standards & Security**: Follow doc conventions. Never introduce secrets or PII; remove any found in existing documentation.

## Workflow

### 1. Context Gathering & Spec Resolution
1. **Resolve `<SpecName>` deterministically**:
   - Use input `<SpecName>` if provided.
   - Else scan `docs/specs/` (or `docs/`) for `review.md` with an explicit approved verdict: a line matching the canonical regex `^[[:space:]]*#*[[:space:]]*[-*]?[[:space:]]*(Status|Verdict)[[:space:]]*:[[:space:]]*APPROVED[[:space:]]*$` (case-insensitive; accepts the markdown heading form `## Status: APPROVED` and list form `- Verdict: APPROVED`). This regex is defined once in `<skill_dir>/scripts/gather-context.sh` (`APPROVED_REGEX`), which is the single source of truth — never use a looser or stricter match. A bare `APPROVED` line does not count.
   - If multiple match, choose latest by name/timestamp. If none match, fail explicitly.
   - *(Optional helper: run `<skill_dir>/scripts/gather-context.sh [<SpecName>]`)*.
2. **Process Artifacts**: Read available artifacts (`spec.md`, `plan.md`, `review.md`). If any artifact is missing, skip it, note in summary, and rely on code diff as source of truth.
3. **Inspect Code Changes & Scope Filter**:
   - In git repos: inspect diff from baseline (`git merge-base HEAD main/master`, commit of `review.md`, or `HEAD~1`).
   - Exclude vendor, build outputs, lockfiles, and generated files (`vendor/`, `dist/`, `node_modules/`, `*.lock`, `*_generated.*`).
   - If the diff is large (more than ~40 in-scope files): list all in-scope files and flag the diff size in the summary. Never silently truncate the file list.
   - Non-git fallback: inspect changed files manually and note lack of git history.
   - Track added, modified, renamed, and removed components.

### 2. In-Code Documentation
For all in-scope modified and newly added source files:
- **Class/Module Headers**: Purpose, context, and spec relation.
- **Public APIs**: Contracts, parameters, returns, exceptions, thread-safety, and design rationale.
- **Complex Private/Protected Methods**: Logic flow, invariants, algorithms, and state mutations.
- **Gotchas & Quirks (Mandatory)**: Prominently flag non-obvious behaviors, divergences from spec, workarounds, or edge cases (`// GOTCHA:`, `// WARNING:`, `/** @implNote GOTCHA: */`).

### 3. Project-Level Documentation
- **README Files**: Update root and module `README.md` for new endpoints, configs, CLI flags, or prerequisites.
- **Removed/Renamed Features**: Delete or update all references to removed or renamed features across guides and READMEs.
- **Project Docs (`docs/`)**: Update domain guides (schemas, APIs, conventions) or create guides for major new subsystems.

### 4. Verification & Summary
1. Run project build/compile/test command to verify doc syntax, linting, and doc-tests.
2. Present a structured summary to the user:
   - **Spec & Artifacts**: Resolved `<SpecName>`, baseline ref, and missing artifacts skipped.
   - **In-Code Docs & Gotchas**: Documented files, public APIs, complex methods, and flagged gotchas/divergences/truncations.
   - **Project Docs**: Updated/created/cleaned docs and READMEs.
