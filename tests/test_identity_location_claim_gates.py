"""Synthetic-only regressions for the October identity/location/claim audit."""
import hashlib
import json
from pathlib import Path

import pytest

from test_quantitative_review_workbook import assessed_records, _template
from test_workflow_audit_repairs import bundle, project_at
from src.schemas.claim import ClaimImportance, ClaimStatus
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence, EvidenceLocation, ExtractionMethod
from src.schemas.outline import Outline, OutlineSection
from src.schemas.source import Source
from src.tools.source_content import inspect_source, located_excerpt, recheck_quote, resolve_location
from src.tools.quantitative_review_workbook import build_quantitative_review_workbook
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.gates import check_document_quality, check_input_references


def replace_artifact(source, text):
    path = Path(source.retrieval_path)
    path.write_text(text, encoding="utf-8")
    source.metadata["retrieval"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("mention", ["References\n{title}", "Bibliography\n{doi}", "Daftar Pustaka\n{title} {doi}", "Introduction\nWe cite {doi} here."])
def test_referenced_identity_is_not_primary(tmp_path, mention):
    source = bundle(tmp_path)[0][0]; source.doi = "10.1234/synthetic.target"
    replace_artifact(source, "# Other synthetic article\n" + mention.format(title=source.title, doi=source.doi) + "\nMethods\nOther method.\nResults\nOther result.\nReferences\nOther reference.")
    proof = inspect_source(source)
    assert not proof["identity"] and not proof["full_text"] and proof["findings"]


@pytest.mark.parametrize("title", ["SYNTHETIC STUDY 0", "Synthetic\nStudy   0", "Synthetic: study 0!"])
def test_primary_title_normalization(tmp_path, title):
    source = bundle(tmp_path)[0][0]
    replace_artifact(source, title + "\nMethods\nSynthetic method.\nResults\nSynthetic result.\nReferences\nSynthetic reference.")
    assert inspect_source(source)["identity"] and inspect_source(source)["full_text"]


def test_ambiguous_title_and_conflicting_doi_need_review(tmp_path):
    source = bundle(tmp_path)[0][0]; source.doi = "10.1234/target"
    replace_artifact(source, f"# {source.title}\n# Another article\nMethods\nMethod.\nResults\nResult.\nReferences\nReference.")
    assert not inspect_source(source)["identity"]
    replace_artifact(source, f"Other primary title\n{source.title}\nMethods\nMethod.\nResults\nResult.\nReferences\nReference.")
    assert not inspect_source(source)["identity"]
    replace_artifact(source, f"{source.title}\nDOI: 10.1234/other\nMethods\nMethod.\nResults\nResult.\nReferences\nReference.")
    assert not inspect_source(source)["identity"]


@pytest.mark.parametrize("metadata", ["Authors: Other, A.", "Year: 2020"])
def test_available_primary_author_and_year_must_agree(tmp_path, metadata):
    source = bundle(tmp_path)[0][0]
    replace_artifact(source, f"{source.title}\n{metadata}\nMethods\nMethod.\nResults\nResult.\nReferences\nReference.")
    assert not inspect_source(source)["identity"]


@pytest.mark.parametrize("title,valid", [("Synthetic target article", True), ("Other synthetic article", False)])
def test_retrieval_uses_primary_identity_and_preserves_partial_artifact(tmp_path, title, valid):
    from src.tools.retrieval import RetrievalTool, RetrievalRequest, RetrievedPayload
    source = Source(title="Synthetic target article", url="https://example.invalid/synthetic", state="METADATA_VERIFIED")
    html = f"<h1>{title}</h1><h2>Methods</h2><p>Synthetic method.</p><h2>Results</h2><p>Synthetic result.</p><h2>Discussion</h2><p>Synthetic discussion.</p><h2>References</h2><p>Synthetic target article</p>".encode()
    response = RetrievalTool(fetcher=lambda *args: RetrievedPayload(html, "text/html")).execute(RetrievalRequest(project=project_at(tmp_path), source=source))
    assert response.success and Path(response.document_path).is_file()
    assert response.metadata["source_content"]["identity"] == valid
    assert (source.state == "FULLTEXT_RETRIEVED") == valid
    if not valid: assert source.state == "NEEDS_HUMAN_REVIEW" and source.retrieval_status == "PARTIAL"


def mapped_text():
    first = "Synthetic title\nMethods\nActual methods evidence.\n"
    second = "Results\nActual results evidence.\nDiscussion\nActual discussion evidence.\nReferences\nRef."
    text = first + "\n\n" + second
    return text, [{"page": 1, "text": first, "char_start": 0, "char_end": len(first)}, {"page": 2, "text": second, "char_start": len(first)+2, "char_end": len(text)}]


@pytest.mark.parametrize("location", [{"page": 2}, {"section": "Results"}, {"locator": "p. 2, Results"}, {"page": 2, "section": "Results"}])
def test_real_locations_are_accepted(location):
    text, pages = mapped_text()
    result = located_excerpt(dict(location=location, excerpt="Actual results evidence."), text, pages)
    assert result["sections"] == ["results"]


@pytest.mark.parametrize("location", [{"page": 999}, {"page": 1}, {"section": "Nonexistent"}, {"section": "Methods"}, {"page": 1, "section": "Results"}, {"page": 2, "locator": "p. 1"}, {"char_start": 0, "char_end": 5}, {"char_start": 2, "char_end": 9999}, {"locator": "p. 999, nonexistent section"}, {"paragraph": 999}, {"page_label": "999"}])
def test_wrong_or_conflicting_locations_fail(location):
    text, pages = mapped_text()
    with pytest.raises(ValueError):
        located_excerpt(dict(location=location, excerpt="Actual results evidence."), text, pages)


def test_character_range_and_page_coordinates_are_consistent():
    text, pages = mapped_text(); start = text.index("Actual results")
    location = {"page": 2, "section": "Results", "char_start": start, "char_end": start + len("Actual results evidence.")}
    assert located_excerpt(dict(location=location, excerpt="Actual results evidence."), text, pages)["text"] == "Actual results evidence."
    with pytest.raises(ValueError):
        resolve_location(text, pages, dict(location, page=1))


def test_pdf_artifact_uses_the_actual_parser_page_map(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    records, _ = assessed_records(1, tmp_path, _template()); source = Source.model_validate(records[0]["source_snapshot"])
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    for lines in ([source.title, "Methods", "Synthetic methods evidence."], ["Results", "Fixture result.", "Discussion", "Fixture discussion.", "References", "Synthetic reference."]):
        page = writer.add_blank_page(width=600, height=800)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 50 700 Td " + " 0 -20 Td ".join(f"({line}) Tj" for line in lines) + " ET").encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "synthetic.pdf"; writer.write(path); source.retrieval_path = str(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest(); source.metadata["retrieval"]["sha256"] = digest
    for key in ("examination", "eligibility_review"): source.metadata[key]["artifact_sha256"] = digest
    proof = inspect_source(source)
    assert proof["fully_read"] and proof["identity"]
    evidence = Evidence(claim_id="clm_synthetic", source_id=source.id, evidence_text="Fixture result.", location=EvidenceLocation(page=2, section="Results"))
    assert recheck_quote(source, evidence)
    evidence.location = EvidenceLocation(page=1, section="Results")
    assert not recheck_quote(source, evidence)


@pytest.mark.parametrize("inspection", ["examination", "eligibility_review", "assessment"])
def test_false_locations_never_establish_reading_eligibility_or_scoring(tmp_path, inspection):
    records, template = assessed_records(1, tmp_path, _template())
    source = Source.model_validate(records[0]["source_snapshot"])
    entries = records[0]["assessment"]["criteria"] if inspection == "assessment" else source.metadata[inspection]["sections"]
    for index, entry in enumerate(entries):
        entry["locator"] = f"p. {999+index}, nonexistent section"
    records[0]["source_snapshot"] = source.model_dump(mode="json")
    result = build_quantitative_review_workbook(records, tmp_path / "review.xlsx", template_path=template, require_free_full_text=True)
    assert result.status == "PARTIAL" and result.ranked_count == 0
    proof = inspect_source(source)
    if inspection == "examination": assert not proof["fully_read"]
    if inspection == "eligibility_review": assert not proof["scientific_eligible"]


def test_whole_document_window_does_not_fabricate_reading_coverage(tmp_path):
    records, _ = assessed_records(1, tmp_path, _template()); source = Source.model_validate(records[0]["source_snapshot"])
    for entry in source.metadata["examination"]["sections"]:
        entry.update(locator="body", excerpt="Synthetic methods evidence.")
    assert not inspect_source(source)["fully_read"]


def test_quote_checks_all_coordinates_and_abstract_depth_is_independent(tmp_path):
    records, _ = assessed_records(1, tmp_path, _template()); source = Source.model_validate(records[0]["source_snapshot"])
    evidence = bundle(tmp_path / "other")[2][0]; evidence.source_id = source.id
    evidence.extraction_method = ExtractionMethod.VERBATIM_FULLTEXT; evidence.evidence_text = "Fixture result."
    evidence.location = EvidenceLocation(section="Results", locator="p. 999")
    assert not recheck_quote(source, evidence) and not evidence.quote_verified
    evidence.extraction_method = ExtractionMethod.VERBATIM_ABSTRACT; evidence.evidence_text = source.abstract
    evidence.location = EvidenceLocation(section="Abstract")
    assert recheck_quote(source, evidence) and inspect_source(source)["fully_read"]
    evidence.location = EvidenceLocation(section="Abstract", page=999)
    assert not recheck_quote(source, evidence)


def test_extractor_does_not_trust_caller_haystack_or_false_locator(tmp_path):
    from src.tools.evidence_extractor import EvidenceExtractor
    records, _ = assessed_records(1, tmp_path, _template()); source = Source.model_validate(records[0]["source_snapshot"])
    result = EvidenceExtractor().extract_verbatim(source=source, claim_id="clm_synthetic", passage="Fixture result.", haystack="Fixture result.", location=EvidenceLocation(locator="p. 999"))
    assert result.found and not result.evidence.quote_verified and result.evidence.notes


def test_original_missing_ids_and_high_claim_survive_audit(tmp_path):
    project = project_at(tmp_path); sources, claims, evidence, outline = bundle(project.directory)
    broken = claims[0].model_copy(deep=True); broken.id = "clm_missing"; broken.importance = ClaimImportance.HIGH
    broken.supporting_sources = ["src_missing"]; broken.supporting_evidence = ["evd_missing"]
    bad = evidence[0].model_copy(deep=True); bad.id = "evd_missing"; bad.claim_id = broken.id; bad.source_id = "src_missing"
    outline.sections[0].claim_ids.append(broken.id)
    response = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=project, sources=sources, claims=claims+[broken], evidence=evidence+[bad], outline=outline))
    assert response.metadata["execution_success"] and response.metadata["result_status"] == "PARTIAL"
    assert not response.metadata["finalization_allowed"] and response.needs_human_review and not response.docx_path
    log = json.loads((Path(response.run_dir) / "claim_screening.json").read_text(encoding="utf-8"))
    assert any("src_missing" in f for f in log["input_integrity"])
    assert any(d["claim_id"] == broken.id and d["decision"] == "lost_all_support" for d in log["decisions"])
    bad.claim_id = "clm_nonexistent"
    assert any("clm_nonexistent" in f for f in check_input_references(claims=claims, sources=sources, evidence=[bad]).violations)


def test_screened_support_is_reassessed_and_corpus_preserved(tmp_path):
    project = project_at(tmp_path); records, template = assessed_records(2, project.directory, _template())
    sources = [Source.model_validate(r["source_snapshot"]) for r in records]
    sources[1].metadata.pop("eligibility_review")
    _, claims, evidence, outline = bundle(project.directory / "claims")
    claim = claims[0]; claim.supporting_sources = [s.id for s in sources]; claim.supporting_evidence = [evidence[0].id, "evd_second"]; claim.required_source_count = 2
    evidence[0].source_id = sources[0].id
    second = evidence[0].model_copy(deep=True); second.id = "evd_second"; second.source_id = sources[1].id
    response = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=project, sources=sources, claims=claims, evidence=evidence+[second], outline=outline, require_free_full_text=True))
    decision = response.metadata["claim_screening"][0]
    assert decision["decision"] == "support_reassessed" and decision["result_status"] == "INSUFFICIENT_EVIDENCE"
    assert not response.metadata["finalization_allowed"]
    assert len(json.loads((Path(response.run_dir) / "sources_snapshot.json").read_text(encoding="utf-8"))) == 2
    assert claim.status == ClaimStatus.SUPPORTED  # Original input is not rewritten.


def test_recorded_withdrawal_with_revised_outline_can_finish(tmp_path):
    project = project_at(tmp_path); sources, claims, evidence, outline = bundle(project.directory, 2)
    claims[1].transition_to(ClaimStatus.WITHDRAWN, reason="Synthetic scope revision; remove secondary argument from outline", actor="synthetic reviewer")
    outline.sections[0].claim_ids = [claims[0].id]
    response = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=project, sources=sources, claims=claims, evidence=evidence, outline=outline))
    assert response.metadata["finalization_allowed"] and response.docx_path
    assert response.metadata["claim_screening"][0]["decision"] == "recorded_withdrawal"
    from src.workflows.export_bundle import export_bundle
    import zipfile
    exported = export_bundle(project.directory, run_id=response.run_id)
    assert exported["success"]
    with zipfile.ZipFile(exported["bundle_path"]) as archive:
        assert archive.testzip() is None
        assert "run/claim_screening.json" in archive.namelist()


def test_outline_missing_claim_is_a_finding(tmp_path):
    sources, claims, evidence, outline = bundle(tmp_path)
    outline.sections[0].claim_ids.append("clm_missing")
    assert any("outline" in v and "clm_missing" in v for v in check_input_references(claims=claims, evidence=evidence, sources=sources, outline=outline).violations)


def test_recorded_withdrawal_resolves_missing_support_without_hiding_original_audit(tmp_path):
    project = project_at(tmp_path); sources, claims, evidence, outline = bundle(project.directory, 2)
    claims[1].supporting_sources = ["src_missing"]; evidence[1].source_id = "src_missing"
    claims[1].importance = ClaimImportance.HIGH
    claims[1].transition_to(ClaimStatus.WITHDRAWN, reason="Synthetic explicit scope revision: remove unsupported argument", actor="synthetic reviewer")
    outline.sections[0].claim_ids = [claims[0].id]
    result = AcademicWritingWorkflow().execute(AcademicWritingRequest(project=project, sources=sources, claims=claims, evidence=evidence, outline=outline))
    assert result.metadata["finalization_allowed"] and result.docx_path
    assert result.metadata["input_integrity"] and result.metadata["resolved_input_integrity"]
    log = json.loads((Path(result.run_dir) / "claim_screening.json").read_text(encoding="utf-8"))
    assert any("src_missing" in finding for finding in log["resolved_by_recorded_withdrawal"])


@pytest.mark.parametrize("methods,limitations", [("Metode", "Keterbatasan"), ("Metode Penelusuran Literatur", "Keterbatasan Literatur")])
def test_quality_aliases_and_nested_content_are_recognized(tmp_path, methods, limitations):
    project = project_at(tmp_path); project.output_type = "literature_review"
    draft = f"# Synthetic review\n## Pendahuluan\nIntro.\n## {methods}\n### Penelusuran\nHanya full-text legal gratis.\n## Hasil\nResult.\n## {limitations}\nTerbatas pada akses gratis.\n## Kesimpulan\nConclusion.\n## Referensi\nSynthetic references."
    assert check_document_quality(draft, project)["passed"]
    project.required_sections = [methods, limitations]
    project.research_options["require_free_full_text"] = True
    findings = check_document_quality(draft, project)["findings"]
    assert not any("disclose" in f or "required section" in f for f in findings)
    assert not check_document_quality(draft.replace("Intro.", ""), project)["passed"]


def test_custom_sections_and_unrelated_headings(tmp_path):
    project = project_at(tmp_path); project.output_type = "literature_review"
    result = check_document_quality("## Metode Pembayaran\nPaid.\n## Keterbatasan Anggaran\nBudget.", project)
    assert any(f.endswith(": metode") for f in result["findings"])
    assert any(f.endswith(": keterbatasan") for f in result["findings"])
    project.output_type = "search_report"; project.required_sections = ["Strategi Pencarian"]
    assert check_document_quality("## Strategi Pencarian\nSynthetic search protocol.", project)["passed"]
    assert not check_document_quality("## Strategi Pencarian\n", project)["passed"]
    project.required_sections = ["Metode"]
    assert not check_document_quality("## Metode\n## Metode Penelusuran Literatur\nSynthetic method.", project)["passed"]


def test_documented_synthetic_input_matches_schema_and_stays_partial(tmp_path):
    payload = json.loads((Path(__file__).parents[1] / "skills/autonomi-agentic-ilmiah/references/input-synthetic.json").read_text(encoding="utf-8-sig"))
    request = AcademicWritingRequest.model_validate(payload)
    request.project.path = str(project_at(tmp_path).directory)
    result = AcademicWritingWorkflow().execute(request)
    assert result.metadata["execution_success"] and result.metadata["result_status"] == "PARTIAL"
    assert not result.metadata["finalization_allowed"] and not result.docx_path


def test_valid_synthetic_review_with_verified_rubric_can_finalize(tmp_path):
    project = project_at(tmp_path); project.output_type = "literature_review"
    records, template = assessed_records(3, project.directory, _template())
    sources = [Source.model_validate(r["source_snapshot"]) for r in records]
    claim_sources = sources + [sources[0]] * 4
    claims = [Claim(id=f"clm_valid_{i}", claim_text=s.abstract, status="SUPPORTED", supporting_sources=[s.id], supporting_evidence=[f"evd_valid_{i}"], qualifier="SYNTHETIC TEST ONLY; lingkup akses gratis") for i,s in enumerate(claim_sources)]
    evidence = [Evidence(id=c.supporting_evidence[0], claim_id=c.id, source_id=s.id, evidence_text=s.abstract, extraction_method="VERBATIM_ABSTRACT", location=EvidenceLocation(section="Abstract")) for c,s in zip(claims,claim_sources)]
    outline = Outline(title="SYNTHETIC TEST ONLY", sections=[
        OutlineSection(title="Pendahuluan", claim_ids=[claims[3].id]),
        OutlineSection(title="Metode Penelusuran Literatur", claim_ids=[claims[4].id]),
        OutlineSection(title="Hasil", claim_ids=[c.id for c in claims[:3]]),
        OutlineSection(title="Keterbatasan Literatur", claim_ids=[claims[5].id]),
        OutlineSection(title="Kesimpulan", claim_ids=[claims[6].id])])
    request = AcademicWritingRequest(project=project, sources=sources, claims=claims, evidence=evidence, outline=outline, quantitative_review=True,
        quantitative_review_template=str(template), quantitative_review_records=records, require_free_full_text=True)
    response = AcademicWritingWorkflow().execute(request)
    assert response.metadata["execution_success"] and response.metadata["result_status"] == "PASS", response.review_prompt
    assert response.metadata["finalization_allowed"] and response.docx_path
    assert response.metadata["quantitative_review"]["ranked_count"] == 3
