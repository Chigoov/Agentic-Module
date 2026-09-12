"""Unit tests for the AAI launcher scripts and skill documentation."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_aai_launcher_files_exist() -> None:
    root = _repo_root()
    assert (root / "aai.bat").is_file(), "aai.bat must exist in repo root"
    assert (root / "aai.ps1").is_file(), "aai.ps1 must exist in repo root"


def test_aai_launchers_have_no_hardcoded_user_paths() -> None:
    root = _repo_root()
    bat_content = (root / "aai.bat").read_text(encoding="utf-8")
    ps1_content = (root / "aai.ps1").read_text(encoding="utf-8")

    forbidden_patterns = ["C:\\Users", "c:\\users", "HYPE AMD", "hype amd"]
    for pattern in forbidden_patterns:
        assert pattern not in bat_content, f"aai.bat contains hardcoded path '{pattern}'"
        assert pattern not in ps1_content, f"aai.ps1 contains hardcoded path '{pattern}'"

    # Ensure essential commands are handled
    for cmd in ["check", "open", "monitor", "run", "runs", "bundle", "help"]:
        assert f'"{cmd}"' in ps1_content or f"'{cmd}'" in ps1_content, f"aai.ps1 must handle '{cmd}' command"


def test_aai_skill_documentation_covers_mandatory_audits() -> None:
    root = _repo_root()
    main_skill = root / "skills" / "autonomi-agentic-ilmiah" / "SKILL.md"
    alias_skill = root / "skills" / "aai" / "SKILL.md"

    assert main_skill.is_file(), "skills/autonomi-agentic-ilmiah/SKILL.md must exist"
    assert alias_skill.is_file(), "skills/aai/SKILL.md must exist"

    main_text = main_skill.read_text(encoding="utf-8")
    alias_text = alias_skill.read_text(encoding="utf-8")

    # Mandatory audits and concepts must be present in documentation
    for item in ["citation_audit.json", "fact_audit.json", "AAI", "final.docx"]:
        assert item in main_text, f"Main skill documentation must mention '{item}'"
        assert item in alias_text, f"Alias skill documentation must mention '{item}'"

    # Token leakage and anti-fabrication rules
    assert "turn..." in main_text, "Main skill documentation must warn against internal tokens"
    assert "aai.bat" in main_text, "Main skill documentation must document aai.bat launcher"
    assert "aai.bat" in alias_text, "Alias skill documentation must document aai.bat launcher"
