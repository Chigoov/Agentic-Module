# Prompts

Directory for reusable, version-controlled prompt templates used by the
autonomous academic research workflow (system prompting, agent orchestration,
evidence-gathering instruction sets).

## Status

- **Created**: Phase 3 architecture refactor (R-clarity / M4).
- **Population**: Intentional placeholder. Prompt templates will be added as
  the workflow engine matures, once concrete orchestration patterns are
  designed against the authoritative transition contract in
  `src/workflows/__init__.py`.

## Convention

- Store one prompt template per `.md`/`.txt` file, with a short header
  describing its intended consumer, version, and any guardrails.
- Keep prompt content deterministic and reproducible; reference spec anchors
  (e.g. `00_MASTER_INSTRUCTION.md` section numbers) rather than duplicating
  authority.
