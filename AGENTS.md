# Auditor Support Tool: development guide

## Purpose

Reusable Windows desktop application for data-led auditing, intended to support
multiple audit domains and dataset types beyond General Ledger. It helps auditors
identify transactions, records and patterns requiring scrutiny while preserving
evidence traceability, reproducibility and auditor professional judgement.

Intended workflow: source audit data → profiling and preparation → field mapping
→ procedure readiness → deterministic execution → traceable exceptions and metrics
→ auditor-facing results → reproducible Audit Procedure Report → optional
controlled AI-assisted analysis.

## Primary architectural rule

**The Test Engine knows how to run an audit procedure,
but does not know how any particular audit test works.**

Keep generic Test Engine/core infrastructure procedure-neutral. Duplicate invoice,
weekend transaction, segregation of duties, unmapped account and future audit-test
rules belong in their domain procedure implementations, never generic core services
or GUI code.

## Audit integrity

- Deterministic procedures determine exception membership.
- Presenters may explain results but must not redefine exception membership.
- AI may analyse completed results but must not determine or redefine exceptions.
- An exception does not automatically establish fraud, non-compliance, error,
  control failure, misstatement or a confirmed audit finding.
- Preserve source-record/source-row traceability and reproducibility controls.

## Current architecture and flow

Source/import → workbook package/datasets → profiling → preparation → field mapping
→ PreparedAuditDataset (AuditRecordSource) → procedure availability/readiness
→ ProcedureDatasetResolver / ProcedureDatasetBundle where required
→ TestEngineService → execution service → registered domain procedure
→ ProcedureResult.

The result branches into:

- Presenter registry → dashboard presentation → ResultsPage.
- AuditProcedureReportBuilder → AuditProcedureReport → report display or optional
  OpenWebUI handoff. Report generation uses the underlying result, not filtered
  presentation rows.

Key ownership under `src/auditor_support_tool/`:

- `core/`: data/workspace services, contracts, readiness, resolution, execution and
  structured reporting; no procedure-specific detection rules.
- `domains/financial_audit/general_ledger/procedures/`: executable GL audit rules.
- `presentation/`: result explanations and display models.
- `gui/`: user interaction and orchestration; keep expensive work off the GUI thread.
- `services/`: external integrations, credentials and operating-system services.

## Important implementation facts

- GL001, GL003, GL006 and GL011 are executable and regression tested. Catalogue entries
  alone do not imply executable implementations.
- GL011 tests GL account existence against a Chart of Accounts using generic
  multi-dataset execution; exception membership remains GL transaction-level.
- Results are presentation-driven and based on deterministic ProcedureResult.
- Structured AuditProcedureReport generation exists.
- Workspaces retain configuration and execution stamps, not full execution results.
- OpenWebUI integration exists and is under active development. Report evidence
  can be uploaded and embedded directly for analysis.
- The General Ledger baseline in `tests/fixtures/regression/general_ledger/`
  protects deterministic behaviour; change expectations only for reviewed rule changes.
- Currently GL003 applies audit-period filtering; GL001 and GL006 record the period
  without filtering by it. GL011 also evaluates the full prepared GL population.
  Do not assume identical scope semantics.

## AI boundary and security

- AI numerical patterns must be evidence-grounded, with explicit denominators,
  relevant field rules and source references where applicable.
- Never silently truncate or omit audit evidence. Model context limits are not
  evidence-completeness guarantees. Current handoff rejects evidence over 64 KiB;
  this byte cap does not guarantee that a model can consume all evidence.
- OpenWebUI API keys must remain in Windows Credential Manager, never QSettings,
  workspace files, source code, logs or Git-tracked files.
- Treat audit evidence as potentially confidential. Avoid exposing credentials or
  sensitive server responses in errors; do not reflect raw responses blindly.
- Do not weaken source-integrity or fingerprint controls.

## Reproducibility

Preserve source SHA-256, mapping fingerprints, combined dataset mapping
fingerprints, procedure versions, parameters, audit period, execution metadata,
source record IDs, source row numbers, report fingerprints and AI evidence hashes
where applicable. Hashes are integrity/fingerprint mechanisms, not digital signatures.

The report fingerprint excludes its own field and only the execution ID and
creation timestamp from reproducibility metadata. Other report content remains
significant. AI evidence hashing covers the actual evidence envelope and is a
separate mechanism. Preserve these distinctions when changing serialization.

## Development workflow

Before changing existing behaviour:

1. Read this file and inspect the exact current implementation.
2. Search important callers/usages and inspect relevant tests.
3. Identify the owning architectural layer and state a short implementation plan.
4. Make the smallest coherent change; avoid unrelated refactoring.
5. Add or update relevant tests and validate the complete repository.

Read existing files rather than reconstructing them from assumptions. Preserve
unrelated working-tree changes.

## Validation

At a natural implementation checkpoint, use the project environment and run:

```powershell
python -m ruff format .\src .\tests
python -m ruff check .\src .\tests
python -m compileall .\src
pytest -q
git diff --check
git status --short
```

Do not claim completion if tests fail. The known review baseline is 484 passing
tests; the current repository suite is authoritative as coverage grows. Respect
explicit read-only or file-scope instructions: formatting mutates files, so do not
run it when those instructions prohibit its effects.

## Git safety

- Do not commit unless the user explicitly requests it.
- Do not push unless the user explicitly requests it.
- Do not rewrite Git history.
- Before proposing a commit, report test results, a Git diff summary and Git status.

## Python compatibility

The supported source range is Python >=3.12,<3.15. Source syntax and Ruff target
Python 3.12; keep multiple exception types parenthesised. Grammar/static checks
for Python 3.12 and 3.13 do not establish runtime compatibility. Runtime validation
must be recorded separately for each installed interpreter; do not claim a fully
validated release matrix until installation and tests pass on all three versions.
