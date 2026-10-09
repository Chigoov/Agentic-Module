"""Recheck stored source artifacts; input flags never establish reading proof."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from src.schemas.evidence import Evidence, EvidenceLocation, ExtractionMethod
from src.schemas.source import Source
from src.tools.pdf_parser import PDFParserTool
from src.tools.source_mapper import best_title_match, normalize_doi, normalize_title


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


_SECTION_NAMES = {"abstract", "abstrak", "introduction", "pendahuluan", "background", "methods", "methodology", "materials and methods", "metode",
    "participants", "measures", "procedure", "statistical analysis", "results", "hasil", "discussion", "pembahasan", "results and discussion",
    "conclusion", "conclusions", "kesimpulan", "limitations", "keterbatasan", "references", "bibliography", "referensi", "daftar pustaka", "acknowledgements"}


def _headings(text):
    headings = []
    for match in re.finditer(r"(?m)^([^\n]+)$", text):
        raw = match[1].strip()
        marked = bool(re.match(r"^(?:#{1,6}\s|\d+(?:\.\d+)*[.)]?\s+)", raw))
        name = re.sub(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+)", "", raw).strip().rstrip(":").casefold()
        if marked or name in _SECTION_NAMES:
            headings.append((name, match.start(), match.end()))
    return headings


def _primary_identity(source, text, declared_titles=None):
    # ponytail: title must be a front-matter title, not a fuzzy body mention.
    # Unusual layouts require review; a DOI anywhere in the body is insufficient.
    cut = next((start for name, start, _ in _headings(text) if name in _SECTION_NAMES), len(text))
    lines = [re.sub(r"^#\s+", "", line.strip()) for line in text[:cut].splitlines() if line.strip()][:30]
    target = normalize_title(source.title)
    primary_titles = [normalize_title(t) for t in declared_titles] if declared_titles is not None else [normalize_title(m[1]) for m in re.finditer(r"(?m)^#\s+(.+)$", text[:cut])]
    if primary_titles and primary_titles != [target]:
        return False, "declared primary title differs from the target or is ambiguous"
    starts = range(len(lines)) if primary_titles else range(min(1, len(lines)))
    candidates = [normalize_title(" ".join(lines[i:j])) for i in starts for j in range(i+1, min(i+12, len(lines))+1)]
    if not target or target not in candidates:
        return False, "primary manuscript title is absent or ambiguous; body/reference mentions do not establish identity"
    # A different DOI explicitly declared in front matter contradicts the title match.
    declared = re.findall(r"(?im)^\s*(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,}/\S+)", text[:cut])
    if source.doi and declared and normalize_doi(source.doi) not in {normalize_doi(d.rstrip('.,;')) for d in declared}:
        return False, "front-matter DOI contradicts the target article"
    authors = re.search(r"(?im)^\s*(?:authors?|penulis)\s*:\s*(.+)$", text[:cut])
    if source.authors and authors and normalize_title(source.authors[0].split(",")[0]) not in normalize_title(authors[1]):
        return False, "declared front-matter author contradicts the target article"
    year = re.search(r"(?im)^\s*(?:year|tahun|publication year|tahun publikasi)\s*:\s*(\d{4})\b", text[:cut])
    if source.year and year and int(year[1]) != source.year:
        return False, "declared front-matter year contradicts the target article"
    return True, None


def resolve_location(text: str, pages: list, location: Mapping | EvidenceLocation | str) -> dict:
    """Resolve all declared coordinates to one intersecting document range.

    Offsets are zero-based/end-exclusive in parsed full_text; page is the
    parser's physical one-based page. Unsupported coordinates fail closed.
    """
    data = location.model_dump(exclude_none=True) if isinstance(location, EvidenceLocation) else ({"locator": location} if isinstance(location, str) else dict(location))
    data = {k:v for k,v in data.items() if v is not None and v != ""}
    locator = str(data.pop("locator", "")).strip()
    if locator and locator.casefold() not in {"body", "full text", "full-text", "document", "retrieved body", "retrieved content"}:
        for part in locator.split(","):
            part = part.strip()
            page = re.fullmatch(r"(?:p\.?|page|halaman)\s*(\d+)", part, re.I)
            key, value = ("page", int(page[1])) if page else ("section", re.sub(r"^(?:section\s*:\s*|§)", "", part, flags=re.I))
            if key in data and str(data[key]).casefold() != str(value).casefold():
                raise ValueError(f"conflicting {key} coordinates")
            data[key] = value
    if not data and not locator:
        raise ValueError("location unspecified")
    if any(k not in {"page", "page_label", "section", "char_start", "char_end"} for k in data):
        raise ValueError("unsupported location coordinate (paragraph/anchor needs an extraction map)")
    ranges = [(0, len(text))]
    if "page_label" in data:
        matching = [p for p in pages if str(p.get("page_label", f"p. {p.get('page')}")) == str(data["page_label"])]
        if len(matching) != 1:
            raise ValueError("page label is unavailable or ambiguous")
        if "page" in data and data["page"] != matching[0]["page"]:
            raise ValueError("page and page_label disagree")
        data["page"] = matching[0]["page"]
    if "page" in data:
        matches = [p for p in pages if p.get("page") == data["page"]]
        if len(matches) != 1:
            raise ValueError(f"page {data['page']} is unavailable or ambiguous")
        page = matches[0]; page_text = page.get("text", "")
        start = page.get("char_start")
        if start is None:
            start = text.find(page_text)
            if text.find(page_text, start+1) != -1:
                raise ValueError("page extraction has ambiguous offsets")
        end = page.get("char_end", start+len(page_text))
        if not page_text or not 0 <= start < end <= len(text) or text[start:end] != page_text:
            raise ValueError("page text/offsets do not match the extraction")
        ranges.append((start, end))
    headings = _headings(text)
    if "section" in data:
        name = str(data["section"]).strip().casefold().rstrip(":")
        found = [(i, h) for i,h in enumerate(headings) if h[0] == name]
        if len(found) != 1:
            raise ValueError(f"section {data['section']!r} is unavailable or ambiguous")
        i, heading = found[0]
        ranges.append((heading[2], headings[i+1][1] if i+1 < len(headings) else len(text)))
    if "char_start" in data or "char_end" in data:
        start, end = data.get("char_start"), data.get("char_end")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 0 <= start < end <= len(text):
            raise ValueError("character range must be valid and within the parsed document")
        ranges.append((start, end))
    start, end = max(r[0] for r in ranges), min(r[1] for r in ranges)
    if start >= end:
        raise ValueError("declared coordinates do not intersect")
    return {"text": text[start:end], "start": start, "end": end,
        "sections": [name for i,(name,_,body_start) in enumerate(headings) if max(start,body_start) < min(end, headings[i+1][1] if i+1<len(headings) else len(text))]}


def _entry_location(entry):
    data = {k:entry[k] for k in ("page", "page_label", "section", "char_start", "char_end", "locator", "paragraph") if k in entry}
    for key, value in (entry.get("location") or {}).items():
        if key in data and data[key] != value:
            raise ValueError(f"conflicting {key} coordinates")
        data[key] = value
    return data


def located_excerpt(entry: Mapping, text: str, pages: list) -> dict:
    located = resolve_location(text, pages, _entry_location(entry))
    excerpt = entry.get("excerpt") or entry.get("evidence_excerpt")
    matches = list(re.finditer(r"\s+".join(re.escape(word) for word in str(excerpt or "").split()), located["text"], re.I)) if excerpt else []
    if len(matches) != 1:
        raise ValueError("excerpt is absent from the declared location")
    # Reading coverage comes from the actual excerpt, not its search window.
    start, end = located["start"] + matches[0].start(), located["start"] + matches[0].end()
    return resolve_location(text, pages, {"char_start": start, "char_end": end})


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
        primary_titles = None
        if path.suffix.lower() == ".pdf" or content.startswith(b"%PDF"):
            parsed = PDFParserTool().parse(content)
            if not parsed.success or not parsed.has_text_layer:
                raise ValueError(parsed.error_message or "PDF is unreadable")
            text = parsed.full_text
            result["pages"] = [p.to_dict() for p in parsed.pages]
        elif path.suffix.lower() in {".html", ".htm"}:
            from src.tools.retrieval import _TextExtractor
            parser = _TextExtractor()
            parser.feed(content.decode("utf-8", errors="replace"))
            text, primary_titles = parser.text(), parser.primary_titles
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
        result["identity"], identity_reason = _primary_identity(source, text, primary_titles)
        if not result["identity"]:
            result["findings"].append(identity_reason)
        groups = (("methods", "methodology", "metode"), ("results", "hasil"), ("discussion", "pembahasan"), ("references", "bibliography", "referensi", "daftar pustaka"))
        headings = [any(re.search(r"(?im)^\s*(?:#{1,6}\s*|\d+[.\d]*\s+)?" + re.escape(word) + r"\s*:?\s*$", text) for word in group) for group in groups]
        complete = headings[0] and headings[3] and (headings[1] or headings[2]) and meta.get("retrieval_method") != "abstract"
        inspection = source.metadata.get("content_inspection") or {}
        if not complete and _inspection_matches(inspection, source, digest, text, result["pages"], result["findings"]):
            coverage = {name for s in inspection["sections"] for name in located_excerpt(s, text, result["pages"])["sections"]}
            complete = inspection.get("document_kind") == "full_text" and inspection.get("scope") == "completeness" and len(coverage - {"abstract", "references", "bibliography"}) >= 3
        error_page = any(marker in norm for marker in ("access denied", "please log in", "sign in to access", "404 not found", "preview only"))
        result["full_text"] = bool(complete and not error_page and result["identity"] and result["readable"])
        if not result["full_text"]:
            result["findings"].append("artifact completeness has not been established")
        rights = stored_metadata(source)
        provider_grant = bool(rights and any(p["record"].get("rights_status") in {"PUBLIC_DOMAIN", "OPEN_LICENSE", "PROVIDER_STATED_FREE"}
            and p["record"].get("access_mode") in {"OPEN_DOWNLOAD", "READ_ONLINE"}
            and (p["record"].get("license_url") or p["record"].get("landing_url")) for p in rights["provider_records"]))
        rights_review = source.metadata.get("rights_inspection") or {}
        inspected_grant = _inspection_matches(rights_review, source, digest, text, result["pages"], result["findings"]) and rights_review.get("legal_free") is True
        result["legal_free"] = bool(result["full_text"] and source.rights_status in {"PUBLIC_DOMAIN", "OPEN_LICENSE", "PROVIDER_STATED_FREE"} and source.access_mode in {"OPEN_DOWNLOAD", "READ_ONLINE"} and (provider_grant or inspected_grant))
        examination = source.metadata.get("examination") or {}
        examined = _inspection_matches(examination, source, digest, text, result["pages"], result["findings"])
        coverage = {name for s in examination.get("sections", []) for name in located_excerpt(s, text, result["pages"])["sections"]} if examined else set()
        methods = bool(coverage & {"methods", "methodology", "materials and methods", "metode"})
        results = bool(coverage & {"results", "hasil", "results and discussion"})
        discussion = bool(coverage & {"discussion", "pembahasan", "conclusion", "conclusions", "kesimpulan", "results and discussion"})
        distinct = len({normalize(s["excerpt"]) for s in examination.get("sections", [])}) if examined else 0
        result["fully_read"] = bool(result["full_text"] and examined and examination.get("scope") == "full" and methods and results and discussion and distinct >= 3)
        if examination and not result["fully_read"]:
            result["findings"].append("full examination requires distinct located methods, results, and discussion/conclusion evidence")
        eligibility = source.metadata.get("eligibility_review") or {}
        result["scientific_eligible"] = bool(result["full_text"] and _inspection_matches(eligibility, source, digest, text, result["pages"], result["findings"])
            and eligibility.get("decision") == "eligible" and {s.get("criterion") for s in eligibility.get("sections", [])} >= {"construct", "population", "design"})
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError) as exc:
        result["findings"].append(f"cannot process artifact: {exc}")
    return result


def _inspection_matches(log: Mapping[str, Any], source: Source, digest: str, text: str, pages=None, findings=None) -> bool:
    if not isinstance(log, dict) or log.get("source_id") != source.id or log.get("artifact_sha256") != digest or not log.get("reviewer") or not log.get("reviewed_at"):
        return False
    sections = log.get("sections", [])
    try:
        if not sections:
            return False
        for section in sections:
            located_excerpt(section, text, pages or [])
        return True
    except (ValueError, TypeError, AttributeError) as exc:
        if findings is not None:
            findings.append(f"inspection location requires verification: {exc}")
        return False


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
                # Abstract-only snapshots have no page map: never ignore a
                # requested page/section just because an abstract is present.
                abstract = "\n".join(abstracts)
                loc = evidence.location.model_dump(exclude_none=True)
                if any(k in loc for k in ("page", "page_label", "char_start", "char_end", "paragraph")):
                    if loc.get("section", "abstract").casefold() not in {"abstract", "abstrak"}:
                        return ""
                    return _located_evidence(inspect_source(source, root), evidence.location.model_copy(update={"section": evidence.location.section or "abstract"}))
                if loc.get("section", "abstract").casefold() not in {"abstract", "abstrak"} or loc.get("locator", "abstract").casefold() not in {"abstract", "abstrak"}:
                    return ""
                return abstract
            return _located_evidence(inspect_source(source, root), evidence.location.model_copy(update={"section": evidence.location.section or "abstract"}))
        return ""
    inspected = inspect_source(source, root)
    if not inspected["full_text"]:
        return ""
    return _located_evidence(inspected, evidence.location)


def _located_evidence(inspected, location):
    if not inspected["full_text"]:
        return ""
    try:
        return resolve_location(inspected["text"], inspected.get("pages", []), location)["text"]
    except (ValueError, TypeError, AttributeError):
        return ""


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
