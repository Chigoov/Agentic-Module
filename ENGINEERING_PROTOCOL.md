# ENGINEERING_PROTOCOL.md

# AUTONOMI AGENTIC ILMIAH

## Engineering Protocol v1.0

Status: Mandatory

## 1. PURPOSE

This document defines the mandatory engineering process for AUTONOMI
AGENTIC ILMIAH.

Engineering priorities:

-   Correctness before speed
-   Maintainability before convenience
-   Traceability before automation
-   Architecture before implementation

## 2. GOLDEN RULE

No implementation may begin before an Architecture Review has been
completed.

Implementation without Architecture Review is prohibited.

## 3. ENGINEERING LIFECYCLE

Every phase MUST execute:

1.  Load Project Memory (when it exists; see §13)
2.  Load ADR (when `docs/adr/` exists)
3.  Load Component Registry (when it exists)
4.  Load Capability Registry (when it exists)
5.  Load Build Registry (when it exists)
6.  Load Health Registry (when it exists)
7.  Review previous phase
8.  Review Technical Debt (when it exists)
9.  Architecture Review
10. Challenge Existing Design
11. Risk Analysis
12. Migration Analysis
13. Implementation Decision
14. Implementation
15. Self Tests
16. Architecture Audit
17. Documentation Update
18. Registry Update (for registries that actually exist)
19. Project Memory Update (when Project Memory exists)
20. Stop

> [!NOTE]
> Steps 1–6 and 18–19 reference **optional** registries. As of the current
> architecture these registries do **not** exist yet (see `SYSTEM_INDEX.md`
> Level 3). A phase must NOT create or update a registry that is not a real
> implemented artifact. When a registry is introduced as a validated data
> contract, these steps become active again automatically.

## 4. PRE-IMPLEMENTATION GATE

Before coding answer:

-   Is the architecture still valid?
-   Is there duplication?
-   Is there unnecessary coupling?
-   Is there premature abstraction?
-   Is there missing abstraction?
-   Is there a simpler solution?
-   Is this backward compatible?
-   Is migration required?
-   Does this increase technical debt?
-   Why is this implementation preferred?

If these questions cannot be answered confidently, implementation should
pause.

## 5. ARCHITECTURE REVIEW FIRST

Every phase begins with Architecture Review.

Review at minimum:

-   Modularity
-   Scalability
-   Maintainability
-   Separation of concerns
-   Dependency direction
-   State management
-   Configuration
-   Testing strategy
-   Documentation consistency

## 6. DESIGN CHALLENGE

For every significant component document:

-   Current Design
-   Problem
-   Alternative
-   Benefits
-   Trade-offs
-   Migration Risk
-   Recommendation

Do not replace architecture automatically.

## 7. IMPLEMENTATION RULES

Implementation must be:

-   Modular
-   Testable
-   Observable
-   Documented
-   Reversible where practical

Avoid:

-   Monolithic files
-   Hidden coupling
-   Hardcoded paths
-   Hidden configuration

## 8. POST-IMPLEMENTATION REVIEW

Verify:

-   Architecture improved
-   Complexity acceptable
-   Tests passed
-   Documentation synchronized
-   Registries synchronized (for registries that actually exist)
-   Project Memory updated (when it exists)
-   ADR updated if required (once `docs/adr/` exists)
-   No critical regression

## 9. ARCHITECTURE AUDIT

Every completed phase ends with Architecture Audit.

Audit:

-   Code quality
-   Architecture quality
-   Documentation quality
-   Test quality
-   Maintainability
-   Extensibility
-   Technical debt

## 10. TECHNICAL DEBT POLICY

Every debt item records (when a Technical Debt ledger exists):

-   ID
-   Description
-   Impact
-   Priority
-   Recommended Resolution
-   Target Phase
-   Status

Until the ledger exists, record debt in `docs/` as a report, not as a
registry entry.

## 11. ADR POLICY

Every significant architectural decision requires an ADR.

Never overwrite ADR history.

ADR entries are created **once** `docs/adr/` is established. Until then,
record decisions in the relevant phase report (`docs/LAPORAN_*.md`) and
reference them there.

## 12. PROJECT MEMORY POLICY

Project Memory is the operational summary of the project.

Update it after every completed phase — **when Project Memory exists as a
real artifact**. Until then, the `project.json` manifest inside each
research project is the authoritative per-project memory, and phase
reports in `docs/` are the authoritative project history.

## 13. REGISTRY POLICY

The following registries are **planned** but not yet implemented:

-   Component Registry
-   Capability Registry
-   Build Registry
-   Health Registry
-   Technical Debt ledger
-   Changelog

A phase must introduce a registry only when the workflow genuinely needs
it, and must implement it as a validated Pydantic contract (not a loose
directory). Until introduced, do not claim these registries exist.

## 14. TESTING POLICY

Every implementation requires:

-   Unit tests
-   Integration tests where applicable
-   Bootstrap validation
-   Import validation
-   Regression awareness

Never claim success without evidence.

## 15. DEFINITION OF DONE

A phase is DONE only when:

-   Implementation completed
-   Tests passed
-   Architecture reviewed
-   Architecture audited
-   Documentation updated
-   Registries updated (for registries that actually exist)
-   Project Memory updated (when it exists)
-   Technical debt recorded (in `docs/` until a ledger exists)
-   Critical blockers resolved or documented

## 16. CONSTITUTIONAL ENGINEERING RULES

Always prefer:

Architecture > Speed

Evidence > Assumption

Review > Impulse

Modularity > Convenience

Documentation > Memory

Maintainability > Short-term Optimization

Scientific Integrity > Automation

## 17. STOP CONDITIONS

Stop and request review when:

-   Architecture conflict
-   High migration risk
-   Destructive operation
-   Unsupported assumption
-   Insufficient evidence
-   Unverified integration
-   Security concern

## 18. FINAL PRINCIPLE

AUTONOMI AGENTIC ILMIAH is an Academic Research Operating System.

Engineering quality is a first-class feature.

Every implementation must strengthen the architecture, not merely
increase the amount of code.
