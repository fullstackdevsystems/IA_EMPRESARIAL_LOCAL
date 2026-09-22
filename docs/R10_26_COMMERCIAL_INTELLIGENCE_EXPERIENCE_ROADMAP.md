# R10.26 — Commercial Intelligence Experience

## Baseline authority

R10.26 starts from the certified R10.25 release:

`0699250cfa4cb90d34ef0ce6b8af97362d4938d4`

R10.25 remains authoritative for governance, deterministic calculation,
multi-tenant isolation, governed SQL, security, backup/restore, large-data
processing, deliverables and local AI integration.

R10.26 extends the certified product. It does not replace those authorities.

## Commercial objective

Turn the existing enterprise capabilities into a coherent experience for a
non-technical business user:

Login
→ understand business state
→ choose a question or action
→ use governed data
→ receive deterministic findings
→ inspect evidence/dashboard
→ obtain PDF/Excel
→ retain the result in Reports.

## REUSE

Reuse without parallel implementations:

- Authentication and sessions.
- Tenant isolation.
- Company profile.
- Users, roles and permissions.
- Governed SQL connections.
- Documents and datasets.
- Enterprise Assistant.
- Governed routing.
- Deterministic analytics.
- Dynamic dashboards.
- PDF and Excel generators.
- Deliverable registry.
- Local AI configuration.
- Readiness.
- Backup and restore.
- Health and diagnostics.

## EXTEND

Extend the existing product experience:

- `/app` as executive commercial home.
- Assistant as Intelligence Center.
- Guided business questions.
- Visibility of available business information.
- Finding → evidence → dashboard → report journey.
- Report organization and commercial context.
- Administration UX integration.

## MISSING EXPERIENCE

The following are experience gaps, not justification for new analytic engines:

- Executive commercial home state.
- Direct guided access to high-value business questions.
- Products in decline as an explicit user journey.
- Customers that stopped buying as an explicit user journey.
- Sales-decline diagnostic as an explicit user journey.
- Consolidated management attention/findings experience.
- Commercial end-to-end UAT.

## R10.26A — Executive Home

Primary implementation target: `/app`.

The home must help a non-technical user answer:

- Is my company environment ready?
- What business information is available?
- What should I do next?
- What questions can I ask immediately?
- Where are my previous results?

Required experience:

1. Executive welcome/context for the current company.
2. Data/readiness state without exposing unnecessary technical terminology.
3. Primary actions:
   - Ask the Assistant.
   - Analyze information.
   - Review available data.
   - Open previous reports.
4. Guided commercial questions:
   - What products are declining?
   - Which customers stopped buying?
   - Why did sales decrease?
   - What changed compared with the previous period?
   - Which customers contribute the most sales?
   - What requires management attention?
5. Guided questions must reuse `/assistant`; no second chat implementation.
6. No calculation logic is added to the home.
7. No LLM receives numeric calculation authority.

### R10.26A acceptance

A non-technical user logging into `/app` can identify the state of the
environment and start a meaningful business-analysis workflow without knowing
internal platform terminology.

## R10.26B — Intelligence Center

Extend the existing Assistant rather than creating another assistant.

Requirements:

- Commercial quick questions.
- Governed source context.
- Evidence visibility.
- Deterministic findings.
- Clear distinction between calculated facts and interpretation.
- Existing feedback/provenance capabilities remain authoritative.

## R10.26C — Finding to Decision

Unify the existing flow:

Business question
→ governed calculation
→ finding
→ evidence
→ dashboard
→ PDF/Excel
→ Reports.

No second dashboard, reporting or calculation engine may be introduced.

## R10.26D — Commercial Operations UX

Polish and integrate existing:

- Company.
- Users and roles.
- Data connections.
- Local AI.
- Appearance.
- Readiness.
- Backup/restore.
- Diagnostics where appropriate.

This phase is UX/integration work, not control-plane replacement.

## R10.26E — Commercial UAT and Certification

Required end-to-end acceptance journey:

Clean install
→ configure company
→ configure administrator
→ connect governed data or upload supported information
→ readiness
→ login
→ executive home
→ business question
→ deterministic answer
→ evidence
→ dashboard
→ PDF/Excel
→ report history
→ backup
→ restore.

Must preserve:

- Multi-tenant isolation.
- Read-only governed SQL.
- Deterministic numeric authority.
- No mandatory LLM dependency.
- No secrets or business data in release artifacts.
- Upgrade compatibility from R10.25.

## Explicit non-goals

R10.26 will NOT:

- Build another frontend stack.
- Build another Assistant.
- Build another BI engine.
- Build another SQL executor.
- Duplicate PDF/Excel generation.
- Replace authentication or tenant governance.
- Give numeric calculation authority to an LLM.
- Re-certify unchanged R10.25 components without regression evidence.

## Implementation order

R10.26A
→ R10.26B
→ R10.26C
→ R10.26D
→ R10.26E.