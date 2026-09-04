# SYSTEM_INDEX.md

# AUTONOMI AGENTIC ILMIAH

## System Documentation Index v1.0

> Entry point for every engineering session. Read this document first,
> then load only the documents required for the current task.

------------------------------------------------------------------------

# PURPOSE

SYSTEM_INDEX.md is the **navigation layer** of the project.

It prevents unnecessary loading of every documentation file and
establishes the authoritative source for each domain. It is a
**reference / process document**, not a live infrastructure component.

> [!NOTE]
> **Reality check.** Earlier revisions of this file listed runtime
> registries (PROJECT_MEMORY, BUILD_REGISTRY, COMPONENT_REGISTRY,
> CAPABILITY_REGISTRY, HEALTH_REGISTRY, TECHNICAL_DEBT, CHANGELOG) and a
> `docs/adr/` directory as if they existed. **They do not exist yet.**
> Those artifacts will be introduced as real data contracts only when a
> phase actually needs them (e.g. orchestration). Until then, this index
> only references documents that are present in the repository. No
> infrastructure is claimed that is not implemented.

------------------------------------------------------------------------

# DOCUMENT HIERARCHY

## Level 0 --- Entry Point

SYSTEM_INDEX.md (this file)

Always load first.

------------------------------------------------------------------------

## Level 1 --- Core Identity (Mandatory Spec Files)

The six files below are the **canonical specification set**. They are the
only documents validated as present by the system health check
(`src/core/paths.py` → `SPEC_FILES`). Every engineering decision traces to
one of them.

### 00_MASTER_INSTRUCTION.md

Purpose:
- System identity
- Vision
- Core objectives
- Filesystem rules
- High-level architecture
- Global operating principles

Load when:
- starting a new engineering session
- system bootstrap
- architectural planning

------------------------------------------------------------------------

### AGENT_CONSTITUTION.md

Purpose:
- Non-negotiable rules
- Academic integrity
- Evidence policy
- Safety rules

Load when:
- making engineering decisions
- implementing research features
- verifying outputs

------------------------------------------------------------------------

### ARCHITECTURE.md

Purpose:
- Layered architecture
- Agents
- Tools
- Adapters
- Workflows
- Responsibilities

Load when changing architecture or adding components.

------------------------------------------------------------------------

### SYSTEM_RULES.md

Purpose:
- Operational rules
- Coding rules
- Verification rules
- Audit rules

------------------------------------------------------------------------

### WORKFLOW.md

Purpose:
- Research lifecycle
- Task state machine
- Source state machine

------------------------------------------------------------------------

### BUILD_PLAN.md

Purpose:
- Development roadmap
- Phase sequencing
- Deliverables

------------------------------------------------------------------------

## Level 2 --- Engineering Process (Reference / Supplementary)

These documents govern *how* the system is built. They are not validated
by the health check, but they are authoritative for process and
documentation style.

### ENGINEERING_PROTOCOL.md

Purpose:
- Mandatory engineering lifecycle
- Architecture Review First
- Pre/Post implementation gates
- Definition of Done

Load before implementing any feature.

------------------------------------------------------------------------

## Level 3 --- Runtime Knowledge (Planned, Not Yet Implemented)

The following runtime registries are **planned** but are implemented only
when the phase that consumes them is built. They are **documented here as
intent, not as existing artifacts.**

- Project Memory (project status summary)
- Build Registry (phase history)
- Component Registry (registered components)
- Capability Registry (implemented capabilities)
- Health Registry (system health)
- Technical Debt (known debt ledger)
- Changelog (version history)
- `docs/adr/` (Architecture Decision Records)

> [!IMPORTANT]
> Creating any of the above is **not** part of the current architecture
> refactor. They will be introduced as real, validated Pydantic contracts
> in a future phase only when a workflow genuinely needs them. Until then,
> do not reference them as if they exist.

------------------------------------------------------------------------

# BOOTSTRAP ORDER

1.  SYSTEM_INDEX.md
2.  AGENT_CONSTITUTION.md
3.  ENGINEERING_PROTOCOL.md
4.  00_MASTER_INSTRUCTION.md
5.  ARCHITECTURE.md
6.  Required spec documents (as needed)
7.  Load only task-specific documentation

Do not load every document unless necessary.

------------------------------------------------------------------------

# TASK TO DOCUMENT MAP

Need identity? → 00_MASTER_INSTRUCTION.md

Need engineering process? → ENGINEERING_PROTOCOL.md

Need immutable rules? → AGENT_CONSTITUTION.md

Need architecture? → ARCHITECTURE.md

Need workflow? → WORKFLOW.md

Need roadmap? → BUILD_PLAN.md

------------------------------------------------------------------------

# SINGLE SOURCE OF TRUTH

Each topic has one authoritative document.

Avoid duplicating information across multiple documents.

If a document must reference another topic, link to the authoritative
document instead of copying content.

------------------------------------------------------------------------

# DOCUMENT UPDATE POLICY

Whenever architecture changes:

1.  Update the authoritative document.
2.  Update CHANGELOG only if it exists (see Level 3 note).
3.  Record significant decisions as ADR **only once** `docs/adr/` exists.

Do not silently change documentation.

------------------------------------------------------------------------

# FINAL PRINCIPLE

SYSTEM_INDEX.md is the navigation layer of AUTONOMI AGENTIC ILMIAH.

Every engineering session begins here. It describes only what exists.
