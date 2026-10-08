"""Recheck stored source artifacts; input flags never establish reading proof."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from src.schemas.evidence import Evidence, ExtractionMethod
from src.schemas.source import Source
from src.tools.pdf_parser import PDFParserTool
from src.tools.source_mapper import best_title_match, normalize_doi


def stored_metadata(source: Source) -> dict[str, Any] | None:
    proof = source.metadata.get("verification_artifact") or {}
    if not isinstance(proof, dict) or not proof.get("path"):
        return None
    try:
        path = Path(proof["path"])
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != proof.get("sha256"):
            return None
        data = json.loads(content)
        if data.get("source_id") != source.id or normalize(data.get("title", "")) != normalize(source.title) or data.get("doi") != source.doi:
            return None
        matches = data.get("provider_records", [])
        from src.core.config import get_config
        threshold = get_config().verification.metadata_match_threshold
        if not data.get("verified_at") or not matches or not all(m.get("provider") and m.get("record", {}).get("title") and best_title_match(source.title, [m["record"]["title"]])[1] >= threshold for m in matches):
            return None
        if source.doi and not any(normalize_doi(m["record"].get("doi")) == normalize_doi(source.doi) for m in matches):
            return None
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def inspect_source(source: Source, root: Path | None = None) -> dict[str, Any]:
    """Validate hash, identity, readable body, retrieval and examination log.

    ponytail: conservative section detection; unusual layouts need an explicit
    content inspection with located excerpts, rather than guessed completeness.
    """
    result: dict[str, Any] = dict(available=False, readable=False, identity=False,
        full_text=False, legal_free=False, fully_read=False, scientific_eligible=False, text="", pages=[], findings=[])
    meta = source.metadata.get("retrieval") or {}
    path = Path(source.retrieval_path or "")
    if not path.is_absolute() and root:
        path = root / path
    if not source.retrieval_path or not path.is_file():
        result["findings"].append("source artifact is missing")
        return result
    try:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        result["sha256"] = digest
        result["path"] = str(path.resolve())
        if not isinstance(meta, dict) or meta.get("sha256") != digest or not meta.get("retrieved_at") or not (meta.get("final_url") or meta.get("origin")):
            result["findings"].append("retrieval provenance/hash requires re-verification")
            return result
        result["available"] = True
        if path.suffix.lower() == ".pdf" or content.startswith(b"%PDF"):
            parsed = PDFParserTool().parse(content)
            if not parsed.success or not parsed.has_text_layer:
                raise ValueError(parsed.error_message or "PDF is unreadable")
            text = parsed.full_text
            result["pages"] = [p.to_dict() for p in parsed.pages]
        elif path.suffix.lower() in {".html", ".htm"}:
            from src.tools.retrieval import RetrievedPayload, RetrievalTool
            text = RetrievalTool._parse(RetrievedPayload(content, "text/html")) or ""
        elif path.suffix.lower() == ".json":
            data = json.loads(content.decode("utf-8"))
            pages = data.get("pages", []) if isinstance(data, dict) else []
            result["pages"] = pages
            text = data.get("full_text") or "\n\n".join(p.get("text", "") for p in pages)
        else:
            text = content.decode("utf-8")
        result["text"] = text
        norm = normalize(text)
        result["readable"] = bool(norm)
        title = normalize(source.title)
        result["identity"] = bool((source.doi and normalize(source.doi) in norm) or (title and title in norm))
        if not result["identity"]:
            result["findings"].append("artifact identity does not match source title/DOI")
        groups = (("methods", "methodology", "metode"), ("results", "hasil"), ("discussion", "pembahasan"), ("references", "bibliography", "referensi", "daftar pustaka"))
        headings = [any(re.search(r"(?im)^\s*(?:#{1,6}\s*|\d+[.\d]*\s+)?" + re.escape(word) + r"\s*:?\s*$", text) for word in group) for group in groups]
        complete = headings[0] and headings[3] and (headings[1] or headings[2]) and meta.get("retrieval_method") != "abstract"
        inspection = source.metadata.get("content_inspection") or {}
        if not complete and _inspection_matches(inspection, source, digest, text):
            complete = inspection.get("document_kind") == "full_text" and inspection.get("scope") == "completeness" and len({s["locator"] for s in inspection["sections"]}) >= 3
        error_page = any(marker in norm for marker in ("access denied", "please log in", "sign in to access", "404 not found", "preview only"))
        result["full_text"] = bool(complete and not error_page and result["identity"] and result["readable"])
        if not result["full_text"]:
            result["findings"].append("artifact completeness has not been established")
        rights = stored_metadata(source)
        provider_grant = bool(rights and any(p["record"].get("rights_status") in {"PUBLIC_DOMAIN", "OPEN_LICENSE", "PROVIDER_STATED_FREE"}
            and p["record"].get("access_mode") in {"OPEN_DOWNLOAD", "READ_ONLINE"}
            and (p["record"].get("license_url") or p["record"].get("landing_url")) for p in rights["provider_records"]))
        rights_review = source.metadata.get("rights_inspection") or {}
        inspected_grant = _inspection_matches(rights_review, source, digest, text) and rights_review.get("legal_free") is True
        result["legal_free"] = bool(result["full_text"] and source.rights_status in {"PUBLIC_DOMAIN", "OPEN_LICENSE", "PROVIDER_STATED_FREE"} and source.access_mode in {"OPEN_DOWNLOAD", "READ_ONLINE"} and (provider_grant or inspected_grant))
        examination = source.metadata.get("examination") or {}
        result["fully_read"] = bool(result["full_text"] and _inspection_matches(examination, source, digest, text) and examination.get("scope") == "full" and len({str(s.get("locator")).casefold() for s in examination.get("sections", [])}) >= 3)
        eligibility = source.metadata.get("eligibility_review") or {}
        result["scientific_eligible"] = bool(result["full_text"] and _inspection_matches(eligibility, source, digest, text)
            and eligibility.get("decision") == "eligible" and {s.get("criterion") for s in eligibility.get("sections", [])} >= {"construct", "population", "design"})
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError) as exc:
        result["findings"].append(f"cannot process artifact: {exc}")
    return result


def _inspection_matches(log: Mapping[str, Any], source: Source, digest: str, text: str) -> bool:
    if not isinstance(log, dict) or log.get("source_id") != source.id or log.get("artifact_sha256") != digest or not log.get("reviewer") or not log.get("reviewed_at"):
        return False
    sections = log.get("sections", [])
    return bool(sections) and all(isinstance(s, dict) and s.get("locator") and s.get("excerpt") and normalize(str(s["excerpt"])) in normalize(text) for s in sections)


def evidence_source_text(source: Source, evidence: Evidence, root: Path | None = None) -> str:
    """Abstract location and source reading depth are independent."""
    if evidence.extraction_method == ExtractionMethod.VERBATIM_ABSTRACT or (
        evidence.extraction_method not in {ExtractionMethod.VERBATIM_FULLTEXT, ExtractionMethod.TABULAR_VALUE}
        and "abstract" in (evidence.location.section or evidence.location.locator or "").casefold()
    ):
        stored = stored_metadata(source)
        if stored:
            abstracts = [p["record"].get("abstract", "") for p in stored["provider_records"]]
            if any(abstracts):
                return "\n".join(abstracts)
            artifact = inspect_source(source, root)
            abstract = source.abstract or ""
            return abstract if abstract and normalize(abstract) in normalize(artifact["text"]) else ""
        return ""
    inspected = inspect_source(source, root)
    if not inspected["full_text"]:
        return ""
    if evidence.location.page is not None:
        return next((p["text"] for p in inspected["pages"] if p.get("page") == evidence.location.page), "")
    text = inspected["text"]
    if evidence.location.char_start is not None and evidence.location.char_end is not None:
        text = text[evidence.location.char_start:evidence.location.char_end]
    if evidence.location.section:
        heading = re.search(r"(?im)^\s*(?:#{1,6}\s*)?" + re.escape(evidence.location.section) + r"\s*$", text)
        if not heading:
            return ""
        text = text[heading.end():]
        next_heading = re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:methods|methodology|results|discussion|references|abstract|metode|hasil|pembahasan|referensi)\s*$", text)
        if next_heading:
            text = text[:next_heading.start()]
    return text


def recheck_quote(source: Source, evidence: Evidence, root: Path | None = None) -> bool:
    return evidence.mark_quote_verified(haystack=evidence_source_text(source, evidence, root), actor="source_snapshot_recheck")


def record_source(record: Mapping[str, Any]) -> Source | None:
    """Workbook records can carry the same Source snapshot as engine records."""
    snapshot = record.get("source_snapshot")
    if isinstance(snapshot, dict):
        return Source.model_validate(snapshot)
    if record.get("source_id") and record.get("title"):
        return Source(id=str(record["source_id"]), title=str(record["title"]), doi=record.get("doi"),
            retrieval_path=record.get("retrieval_path"), rights_status=record.get("rights_status", "UNKNOWN"),
            access_mode=record.get("access_mode", "UNKNOWN"), landing_url=record.get("article_url"),
            license_url=record.get("license_url"), metadata={"retrieval": record.get("retrieval", {}),
                "examination": record.get("examination", {}), "content_inspection": record.get("content_inspection", {})})
    return None


def inspect_record(record: Mapping[str, Any]) -> dict[str, Any]:
    source = record_source(record)
    return inspect_source(source) if source else {"full_text": False, "legal_free": False, "fully_read": False, "scientific_eligible": False, "findings": ["no traceable source snapshot"]}
