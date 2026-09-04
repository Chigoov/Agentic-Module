# SYSTEM_INDEX.md

# AUTONOMI AGENTIC ILMIAH

## System Documentation Index v1.0

> Entry point for every engineering session. Read this document first,
> then load only the documents required for the current task.

------------------------------------------------------------------------

# PURPOSE

SYSTEM_INDEX.md is the navigation layer of the Academic Research
Operating System (AROS).

It prevents unnecessary loading of every documentation file and
establishes the authoritative source for each domain.

------------------------------------------------------------------------

# DOCUMENT HIERARCHY

## Level 0 --- Entry Point

SYSTEM_INDEX.md (this file)

Always load first.

------------------------------------------------------------------------

## Level 1 --- Core Identity

### 00_MASTER_INSTRUCTION.md

Purpose: - System identity - Vision - Core objectives - Filesystem
rules - High-level architecture - Global operating principles

Load when: - starting a new engineering session - system bootstrap -
architectural planning

------------------------------------------------------------------------

### AGENT_CONSTITUTION.md

Purpose: - Non-negotiable rules - Academic integrity - Evidence policy -
Safety rules

Load when: - making engineering decisions - implementing research
features - verifying outputs

------------------------------------------------------------------------

### ENGINEERING_PROTOCOL.md

Purpose: - Mandatory engineering lifecycle - Architecture Review First -
Pre/Post implementation gates - Definition of Done

Load before implementing any feature.

------------------------------------------------------------------------

## Level 2 --- System Design

### ARCHITECTURE.md

Purpose: - Layered architecture - Agents - Tools - Adapters -
Workflows - Responsibilities

Load when changing architecture or adding components.

------------------------------------------------------------------------

### SYSTEM_RULES.md

Purpose: - Operational rules - Coding rules - Verification rules - Audit
rules

------------------------------------------------------------------------

### WORKFLOW.md

Purpose: - Research lifecycle - Task state machine - Source state
machine

------------------------------------------------------------------------

### BUILD_PLAN.md

Purpose: - Development roadmap - Phase sequencing - Deliverables

------------------------------------------------------------------------

## Level 3 --- Runtime Knowledge

### PROJECT_MEMORY

Current project status.

### BUILD_REGISTRY

Phase history.

### COMPONENT_REGISTRY

Registered components.

### CAPABILITY_REGISTRY

Implemented capabilities.

### HEALTH_REGISTRY

System health.

### TECHNICAL_DEBT

Known debt.

### CHANGELOG

Version history.

### docs/adr/

Architecture Decision Records.

------------------------------------------------------------------------

# BOOTSTRAP ORDER

1.  SYSTEM_INDEX.md
2.  PROJECT_MEMORY
3.  AGENT_CONSTITUTION.md
4.  ENGINEERING_PROTOCOL.md
5.  00_MASTER_INSTRUCTION.md
6.  ARCHITECTURE.md
7.  Required registries
8.  Load only task-specific documentation

Do not load every document unless necessary.

------------------------------------------------------------------------

# TASK TO DOCUMENT MAP

Need identity? → 00_MASTER_INSTRUCTION.md

Need engineering process? → ENGINEERING_PROTOCOL.md

Need immutable rules? → AGENT_CONSTITUTION.md

Need architecture? → ARCHITECTURE.md

Need workflow? → WORKFLOW.md

Need roadmap? → BUILD_PLAN.md

Need project status? → PROJECT_MEMORY

Need architecture history? → docs/adr/

Need technical debt? → TECHNICAL_DEBT

Need component status? → COMPONENT_REGISTRY

Need capability status? → CAPABILITY_REGISTRY

Need build history? → BUILD_REGISTRY

Need system health? → HEALTH_REGISTRY

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
2.  Update PROJECT_MEMORY if project state changes.
3.  Update CHANGELOG.
4.  Create or update ADR.
5.  Update registries if affected.

Do not silently change documentation.

------------------------------------------------------------------------

# FINAL PRINCIPLE

SYSTEM_INDEX.md is the BIOS of the Academic Research Operating System.

Every engineering session begins here.
