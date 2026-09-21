# R10.25 Product Intelligence Evolution - Canonical Roadmap

Status: ACTIVE
Baseline: R10.24 stable
Baseline commit: d6ee11a84f3644b42443d512f6b692465f9d560c

## Governance

- R10.24 remains immutable and is not rewritten by R10.25.
- Phase completion is gate-based, not based on arbitrary numeric weighting.
- A phase reaches 100% only after every required acceptance gate passes.
- Development does not imply commit, push, tag, release, or main promotion.
- Product calculations and governed evidence remain authoritative over generative interpretation.
- Tenant isolation, SQL read-only governance, traceability, and operation without mandatory LLM dependency are preserved.
- Release-candidate identity is assigned only when an actual RC is authorized.

## R10.25A - Baseline and Product Identity Governance

Status: COMPLETED
Goal: establish a truthful and maintainable development authority after R10.24.

Acceptance:
- Product version and development release identity are explicit and non-conflicting.
- R10.24 roadmap reflects its actual certified final state.
- R10.25 has a canonical roadmap.
- Existing R10.24 product contracts remain protected.
- No R10.24 tag, release artifact, or certified evidence is rewritten.

## R10.25B - Governed Business Intelligence Orchestrator

Status: COMPLETED
Goal: coordinate existing governed capabilities from business intent instead of exposing isolated technical workflows.

Scope:
- Interpret business intent.
- Select governed sources and tools.
- Coordinate SQL, files, memory/RAG, semantic definitions, business rules, dashboards, and deliverables.
- Preserve provenance and traceability.
- Degrade safely when AI is unavailable.
- Never allow generative output to override deterministic governed calculations.

## R10.25C - Deeper Business Intelligence

Status: COMPLETED

Goal: produce evidence-backed business findings beyond direct question answering.

Scope:
- Trend and period comparisons.
- Growth and decline detection.
- Customer and product concentration.
- Cancellation and exception analysis.
- Business anomaly signals.
- Ranked opportunities and risks backed by governed evidence.
- Clear separation between calculated facts and AI interpretation.
Closure:
- C1 established governed business-finding classification with rule-supplied finding class and severity; generative AI has no classification authority.
- C2 added deterministic cancellation and exception analysis without inventing status semantics or business thresholds.
- C3 added deterministic statistical anomaly detection using governed executed evidence, without business classification authority.
- C4 added governed risk/opportunity prioritization from explicit rule-supplied classification and severity; rule priority remains rule precedence and is not a finding score or ranking authority.
- C5 certified the productive execution-plan -> dashboard-spec -> business-insights -> business-rule-engine -> governed-business-findings propagation path end to end.
- No parallel BI authority was introduced in the enterprise orchestrator or API.
- Deterministic calculations and governed evidence remain authoritative; LLM output cannot calculate, classify, score, or rank findings.

## R10.25D - Context, Performance and Large Data

Status: NOT STARTED

Goal: improve useful analytical scale and local-model efficiency without weakening governance.

Scope:
- Governed model context budgets.
- Large structured-data handling.
- Retrieval/context selection.
- Provider/model capability-aware execution.
- Memory and vector retrieval efficiency.
- Representative performance measurements.
- Avoid unnecessary whole-dataset or whole-context loading.

## R10.25E - Product Certification

Status: NOT STARTED

Goal: certify R10.25 as a reproducible, supportable evolution of the stable R10.24 product.

Acceptance:
- R10.24 protected regression contracts pass.
- New R10.25 contracts pass.
- Multi-tenant isolation remains valid.
- SQL remains governed and read-only.
- No mandatory LLM dependency is introduced.
- Install, upgrade, backup, restore, and operational lifecycle remain valid.
- Produced release artifact is validated independently from the source tree.
- Release candidate, commit, push, tag, release, and main promotion each require their applicable explicit authorization.

## Deferred / Optional

Controlled fine-tuning remains optional. Existing dataset/run/export infrastructure may be evaluated later, but training a model is not required for R10.25 unless measurable business value justifies adding it to scope.

## Current canonical status

- R10.25A = COMPLETED
- R10.25B = COMPLETED
- R10.25C = COMPLETED
- R10.25D = NOT STARTED
- R10.25E = NOT STARTED

Next component: R10.25D - Context, Performance and Large Data.