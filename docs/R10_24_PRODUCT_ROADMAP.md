# R10.24 Professional Product Experience - Canonical Roadmap

Status: ACTIVE
Canonicalized: 2026-09-19

## Governance

- This document defines the canonical remaining scope of R10.24.
- Phase completion is gate-based, not calculated from arbitrary numeric weighting.
- A phase is 100% only when every defined component is formally accepted.
- No commit, push, tag, release, or main promotion is implied by phase acceptance.
- Existing certified R10.23 RC4 remains frozen until an explicit release decision.

## R10.24A - Unified Product Experience

Status: 100% - FORMALLY CLOSED

## R10.24B - Product Setup and Enterprise Readiness

Status: 100% - FORMALLY CLOSED

Components:
- B1 - 100%
- B2 - 100%
- B3 - 100%
- B4 - 100%

## R10.24C - Core Product Workflows

Status: 100% - FORMALLY CLOSED

Acceptance rule: C is complete only when C1 through C6 are all formally accepted.

Components:
- C1 - Inicio productivo - 100% - FORMALLY CLOSED
- C2 - Asistente productivo - 100% - FORMALLY CLOSED
- C3 - Analizar productivo - 100% - FORMALLY CLOSED
- C4 - Datos productivo - 100% - FORMALLY CLOSED
- C5 - Reportes productivo - 100% - FORMALLY CLOSED
- C6 - Configuración productiva - 100% - FORMALLY CLOSED

No percentage weighting is used inside C. All six required gates passed, therefore C is formally complete.

## R10.24D - Production Operations and Deployment

Status: 0% - NOT STARTED

Goal: make IA Empresarial Local installable, operable, recoverable and maintainable on a real Windows business workstation or server without developer intervention.

Acceptance rule: D is complete only when D1 through D6 are formally accepted.

Components:
- D1 - Clean installation from zero
  - Validated installation entry point for a clean supported Windows environment.
  - Creates required directories and runtime configuration safely.
  - Detects required dependencies and reports actionable missing prerequisites.
  - Does not require manual source-code editing.

- D2 - Runtime and service lifecycle
  - Reliable start, stop, restart and status verification.
  - Product survives normal workstation/server restart according to supported deployment mode.
  - Friendly operational health indication.

- D3 - Dependency and connectivity diagnostics
  - SQL Server connectivity diagnostics.
  - Local AI/Ollama diagnostics when configured.
  - Required ports/services checked without exposing unnecessary technical detail to normal users.
  - Actionable operator diagnostics available when needed.

- D4 - Backup and recovery
  - Backup of governed enterprise configuration and persistent product state.
  - Restore validation.
  - Recovery behavior tested after controlled failure.
  - Tenant/company scope and integrity preserved.

- D5 - Performance and operational observability
  - Measure representative document, database and assistant operations.
  - Record useful latency/health signals.
  - Detect clear degradation/failure without exposing internals in normal product UX.

- D6 - Repair, upgrade and uninstall lifecycle
  - Safe repair/reconfiguration path.
  - Upgrade preserves governed business state.
  - Uninstall behavior is explicit about retained or removed business data.
  - Rollback/recovery path documented and tested.

## R10.24E - Commercial Certification and Release

Status: 0% - NOT STARTED

Goal: certify a reproducible, supportable and publishable commercial build after D is complete.

Acceptance rule: E is complete only when E1 through E5 are formally accepted.

Components:
- E1 - Final security and authorization certification
  - Authenticated product routes.
  - Role/permission enforcement.
  - Company/tenant isolation.
  - No unauthorized cross-scope access.
  - No secrets or technical internals exposed in normal UX.

- E2 - Clean-machine end-to-end certification
  - Install on a clean supported machine or equivalent controlled clean environment.
  - Complete first-run setup.
  - Connect data.
  - Ask business questions.
  - Analyze a file.
  - Generate and download reports.
  - Restart and confirm persistence.

- E3 - Product documentation and support package
  - Installation guide.
  - Operator guide.
  - User guide.
  - Backup/recovery guide.
  - Troubleshooting guide.

- E4 - Reproducible release package
  - Versioned release package.
  - Manifest and SHA-256 verification.
  - Required runtime assets included.
  - No development-only or secret material included.
  - Package validation performed from the produced artifact.

- E5 - Final release authority
  - Final regression suite passes.
  - Release evidence is archived.
  - Git state is clean and release commit is explicitly approved.
  - Tag/release publication occurs only after explicit authorization.

## Current canonical status

- R10.24A = 100%
- R10.24B = 100%
- R10.24C = 100%
- R10.24D = 0%
- R10.24E = 0%

Next component: D1 - Clean installation from zero.
