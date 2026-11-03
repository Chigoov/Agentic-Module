"""Offline QC regressions; fixtures do not represent literature or expert review."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import fixture_source
from src.core.paths import SPEC_FILES, _discover_system_root
from src.core.evidence_registry import EvidenceRegistry
from src.core.errors import ProjectError
from src.runtime.bootstrap import capability_readiness
from src.runtime.progress import read_progress, progress_since
from src.schemas.claim import Claim, SemanticReview
from src.schemas.evidence import Evidence
from src.schemas.project import Project
from src.schemas.source import Source
from src.tools.dedupe import deduplicate
from src.tools.source_content import source_run_cache
from src.tools.verification_tool import VerificationEngine
from src.agents.research import DiscoveryAgent, DiscoveryRequest
from src.tools.research_tool import ResearchResponse


def test_nearest_checkout_wins_over_ancestor_database(tmp_path):
    (tmp_path / 'DATA BASE').mkdir()
    checkout = tmp_path / 'outputs' / 'new-checkout'
    checkout.mkdir(parents=True)
    for marker in SPEC_FILES: (checkout / marker).touch()
    start = checkout / 'src' / 'core'
    start.mkdir(parents=True)
    assert _discover_system_root(start) == checkout


def test_review_fingerprint_binds_text_qualifier_evidence_and_artifact():
    source = Source(id='s', title='Synthetic', metadata={'retrieval': {'sha256':'original'}})
    claim = Claim(id='c', claim_text='Students describe discussions.', supporting_evidence=['e'], supporting_sources=['s'])
    evidence = Evidence(id='e', claim_id='c', source_id='s', evidence_text='Discussions.', location={'section':'Results'})
    baseline = SemanticReview.fingerprint(claim, [evidence], [source])
    for field, value in [('claim_text','Teachers manage classrooms.'), ('qualifier','in one cohort'), ('required_source_count',5)]:
        assert SemanticReview.fingerprint(claim.model_copy(update={field:value}), [evidence], [source]) != baseline
    assert SemanticReview.fingerprint(claim, [evidence.model_copy(update={'location': evidence.location.model_copy(update={'section':'Methods'})})], [source]) != baseline
    source.metadata['retrieval']['sha256'] = 'revised'
    assert SemanticReview.fingerprint(claim, [evidence], [source]) != baseline


def test_registry_repeated_input_is_idempotent_and_revision_requires_new_id(tmp_path):
    project = Project(name='synthetic', workspace='synthetic', path=str(tmp_path))
    evidence = Evidence(id='e', claim_id='c', source_id='s', evidence_text='Original')
    registry = EvidenceRegistry(project, evidence=[evidence])
    assert registry.save() == 1
    assert registry.save() == 0
    revised = evidence.model_copy(update={'evidence_text':'Revised'})
    with pytest.raises(ProjectError, match='new evidence ID'):
        EvidenceRegistry(project, evidence=[revised]).save()
    assert len((tmp_path/'evidence.jsonl').read_text().splitlines()) == 1


def test_dedupe_secondary_index_preserves_conflicting_dois():
    args = dict(title='Same study', authors=['Researcher, A.'], year=2020)
    for reverse in (False, True):
        records = [Source(**args, doi='10.1234/a'), Source(**args)]
        assert len(deduplicate(records[::-1] if reverse else records)) == 1
    assert len(deduplicate([Source(**args,doi='10.1234/a'),Source(**args,doi='10.1234/b')])) == 2


def test_progress_tail_filters_before_limit_and_completes_pending_line(tmp_path):
    path = tmp_path/'progress.jsonl'
    rows = [{'job_id':'first','i':0}] + [{'job_id':'other','i':i} for i in range(20000)]
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"job_id":',encoding='utf-8')
    assert read_progress(tmp_path,limit=1,job_id='first') == rows[:1]
    assert read_progress(tmp_path,limit=3) == rows[-3:]
    first, offset = progress_since(tmp_path)
    assert len(first) == len(rows)
    assert progress_since(tmp_path,offset=offset) == ([],offset)
    with path.open('a') as stream: stream.write('"new"}\n')
    new, after = progress_since(tmp_path,offset=offset)
    assert new == [{'job_id':'new'}] and after > offset
    path.write_text('{"unfinished":',encoding='utf-8')
    assert read_progress(tmp_path) == []


def test_verifier_reuses_one_lookup_per_run_and_invalidates_metadata(tmp_path):
    source = Source(id='s', title='Synthetic title', authors=['A'], year=2020)
    class Provider:
        name = 'synthetic'
        calls = 0
        def lookup_by_bibliographic(self, **kwargs):
            self.calls += 1
            return source.model_copy(deep=True)
    provider = Provider()
    engine = VerificationEngine(providers=[provider])
    with source_run_cache():
        engine.verify(source)
        engine.verify(source)
        assert provider.calls == 1
        source.year = 2021
        engine.verify(source)
        assert provider.calls == 2
    engine.verify(source)
    assert provider.calls == 3


def test_discovery_budget_pagination_filters_and_relevance():
    class Provider:
        name = 'synthetic'
        supports_offset = True
        def execute(self, request):
            return ResearchResponse(results=[Source(title=f'Burnout cohort {request.offset+i}', year=2024, source_type='JOURNAL_ARTICLE') for i in range(request.max_results)])
    result = DiscoveryAgent().execute(DiscoveryRequest(queries=['academic burnout'],concepts=['burnout'],providers=[Provider()],
        max_results_per_query=25, target_sources=40, request_budget=3, year_start=2020,source_types=['JOURNAL_ARTICLE']))
    assert len(result.sources) == 50
    assert result.metadata['requests'] == 2 and result.metadata['stop_reason'] == 'target_reached'
    result = DiscoveryAgent().execute(DiscoveryRequest(queries=['topic'],providers=[Provider()],max_results_per_query=5,target_sources=40,request_budget=2,year_end=2020))
    assert not result.sources and result.metadata['requests'] == 2 and result.metadata['stop_reason'] == 'request_budget_exhausted'
    assert len(result.raw_sources) == 10


def test_disabled_providers_are_structurally_distinct_from_readiness():
    cfg = SimpleNamespace(tools={},verification=SimpleNamespace(enabled=True,min_metadata_providers=1))
    report = capability_readiness('research',config=cfg)
    assert not report['configuration_ready'] and 'crossref' in report['missing_capabilities']
    assert capability_readiness('plan',config=cfg)['configuration_ready']


@pytest.mark.parametrize('workers',[1,2,4])
def test_global_capacity_and_recovery(workers,tmp_path,monkeypatch):
    from src.runtime import execution
    monkeypatch.setattr(execution,'get_paths',lambda:SimpleNamespace(state_dir=tmp_path))
    barrier = threading.Barrier(workers)
    release = threading.Event()
    results = []
    mutex = threading.Lock()
    def run():
        barrier.wait(timeout=5)
        try:
            with execution.workflow_slot():
                with mutex: results.append(True)
                release.wait(timeout=1)
        except execution.WorkflowReadinessError:
            with mutex: results.append(False)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run) for _ in range(workers)]
        for future in futures: future.result(timeout=5)
    assert sum(results) == min(workers,2)
    assert not list((tmp_path/'job_slots').glob('*.lock'))
    with execution.workflow_slot(),execution.workflow_slot(): pass


def test_cooperative_deadline_releases_slot(tmp_path,monkeypatch):
    from src.runtime import execution
    monkeypatch.setattr(execution,'get_paths',lambda:SimpleNamespace(state_dir=tmp_path))
    now = [0]
    monkeypatch.setattr(execution.time,'monotonic',lambda:now[0])
    with pytest.raises(execution.WorkflowReadinessError,match='deadline'):
        with execution.workflow_slot():
            now[0] = 901
            execution.check_workflow_deadline()
    assert not list((tmp_path/'job_slots').glob('*.lock'))


def test_synthetic_research_resume_review_finalize_export(tmp_path,monkeypatch,capsys):
    from src.runtime import cli
    from src.schemas.review import ReviewQueue
    from src.workflows.deep_research import DeepResearchWorkflow, DeepResearchRequest
    from src.agents.research import RetrievalAgentResponse
    from src.workflows.export_bundle import export_bundle
    directory = tmp_path/'project'
    directory.mkdir()
    project = Project(name='synthetic-cycle',workspace='test',path=str(directory),title='Synthetic cycle')
    (directory/'project.json').write_text(project.model_dump_json(),encoding='utf-8')
    quote = 'Students described their learning experiences in interviews.'
    source = fixture_source(Source(id='src_cycle',title='Synthetic interview manuscript',authors=['Researcher, A.'],year=2024,venue='Synthetic Journal',abstract=quote,state='METADATA_VERIFIED'))
    class Provider:
        name = 'synthetic-cycle-provider'
        def lookup_by_bibliographic(self,**kwargs): return source.model_copy(deep=True)
    engine = VerificationEngine(providers=[Provider()])
    claim = Claim(id='clm_cycle',claim_text='Students described learning experiences.',importance=3,status='PARTIALLY_SUPPORTED',qualifier='in these interviews',supporting_sources=[source.id],supporting_evidence=['evd_cycle'])
    evidence = Evidence(id='evd_cycle',claim_id=claim.id,source_id=source.id,evidence_text=quote,evidence_type='DIRECT',strength='MODERATE',reading_depth='ABSTRACT_ONLY',extraction_method='VERBATIM_ABSTRACT',location={'locator':'abstract'})
    monkeypatch.setattr('src.agents.research.RetrievalAgent.execute',lambda self,request:RetrievalAgentResponse(sources=request.sources,parsed_text_by_source={source.id:quote}))
    request = DeepResearchRequest(project=project,user_request='Synthetic interviews',sources=[source],claims=[claim],evidence=[evidence],verification_engine=engine,min_sources=1,generate_docx=False)
    first = DeepResearchWorkflow().execute(request)
    second = DeepResearchWorkflow().execute(request)
    assert not first.success and not second.success
    assert len((directory/'evidence.jsonl').read_text().splitlines()) == 1
    queue = ReviewQueue.load(directory/'review_queue.json')
    assert queue.blocking_items()
    for item in queue.blocking_items():
        assert cli.main(['review-queue',str(directory),'--resolve',item.id,'--decision','PARTIALLY_SUPPORTED','--notes','Synthetic offline assessment of interview statement','--reviewer','test-agent','--reviewer-type','ai']) == 0
    monkeypatch.setattr(cli,'VerificationEngine',lambda:engine)
    capsys.readouterr()
    assert cli.main(['finalize',str(directory)]) == 0
    finalized = json.loads(capsys.readouterr().out)
    assert finalized['metadata']['finalization_allowed'] and Path(finalized['docx_path']).is_file()
    result = export_bundle(directory,run_id=finalized['run_id'])
    assert result['success']


@pytest.mark.parametrize("doi", [None, "10.1234/synthetic"])
def test_supported_source_minimum_counts_publications_not_alias_ids(tmp_path, doi):
    from src.workflows.gates import check_academic_integrity
    source = fixture_source(Source(id='s1',title='Same synthetic study',authors=['A'],year=2020,doi=doi,provider='one',provider_record_id='record-one',state='METADATA_VERIFIED',abstract='Observed finding.'))
    alias = fixture_source(source.model_copy(deep=True,update={'id':'s2','provider':'two','provider_record_id':'record-two'}))
    evidence = [Evidence(id='e'+str(i),claim_id='c',source_id=s.id,evidence_text='Observed finding.',evidence_type='DIRECT',extraction_method='VERBATIM_ABSTRACT',location={'locator':'abstract'}) for i,s in enumerate([source,alias])]
    claim = Claim(id='c',claim_text='Observed finding.',status='SUPPORTED',required_source_count=2,supporting_sources=['s1','s2'],supporting_evidence=[e.id for e in evidence])
    result = check_academic_integrity(claims=[claim],evidence=evidence,sources=[source,alias],root=tmp_path)
    assert any('Only 1 distinct source' in reason for reason in result.violations)
    from src.agents.audit import FactAuditAgent, FactAuditRequest
    project = Project(name='alias-check',workspace='test',path=str(tmp_path))
    audited = FactAuditAgent().execute(FactAuditRequest(project=project,claims=[claim],evidence=evidence,sources=[source,alias]))
    assert not audited.passed and any('Only 1 distinct source' in reason for reason in audited.rejection_reasons)



def test_monitor_rejects_seventeenth_request_thread():
    import socket
    from socketserver import BaseRequestHandler
    from src.runtime.monitor import BoundedMonitorServer
    release = threading.Event()
    ready = threading.Event()
    mutex = threading.Lock()
    count = [0]
    class Handler(BaseRequestHandler):
        def handle(self):
            with mutex:
                count[0] += 1
                if count[0] == 16: ready.set()
            release.wait(timeout=5)
    server = BoundedMonitorServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    clients = []
    try:
        for _ in range(16): clients.append(socket.create_connection(server.server_address,timeout=3))
        assert ready.wait(timeout=5)
        with socket.create_connection(server.server_address,timeout=3) as extra:
            assert b'503 Service Unavailable' in extra.recv(1024)
        assert count[0] == 16
    finally:
        release.set()
        for client in clients: client.close()
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('doi',[None,'10.1234/same-work'])
def test_conflicting_isbns_and_ambiguous_missing_identifier_remain_separate(doi):
    from itertools import permutations
    entries = [{'id':'a','isbn':'9780306406157'}, {'id':'b','isbn':'9780140449136'}, {'id':'missing'}]
    for order in permutations(entries):
        records = [Source(title='Synthetic book',authors=['A'],year=2024,doi=doi,**entry) for entry in order]
        result = deduplicate(records)
        assert len(result) == 3
        assert {s.isbn for s in result if s.isbn} == {'9780306406157','9780140449136'}
    records = [Source(title='Synthetic book',authors=['A'],year=2024,isbn=isbn) for isbn in ['978-0-306-40615-7','9780306406157']]
    assert len(deduplicate(records)) == 1


def test_dedupe_identity_map_does_not_depend_on_representative_choice():
    records = [Source(id='missing',title='Same study',authors=['A'],year=2024,provider='one',provider_record_id='x'),
        Source(id='complete',title='Same study',authors=['A'],year=2024,doi='10.1234/study')]
    for reverse in (False,True):
        identities = {}
        result = deduplicate([s.model_copy(deep=True) for s in (records[::-1] if reverse else records)],identities=identities)
        assert len(result) == 1 and identities == {'missing':'doi:10.1234/study','complete':'doi:10.1234/study'}


def test_rejected_evidence_revision_preserves_current_input_and_valid_revision_resumes(tmp_path,monkeypatch):
    from src.workflows.deep_research import DeepResearchWorkflow,DeepResearchRequest
    from src.agents.research import RetrievalAgentResponse
    directory = tmp_path/'project';directory.mkdir()
    project = Project(name='revision-check',workspace='test',path=str(directory),title='Synthetic revisions')
    (directory/'project.json').write_text(project.model_dump_json(),encoding='utf-8')
    quote = 'Students described their learning experiences in interviews.'
    source = fixture_source(Source(id='src_revision',title='Synthetic interviews',authors=['A'],year=2024,abstract=quote,state='METADATA_VERIFIED'),root=tmp_path/'source')
    claim = Claim(id='clm_revision',claim_text='Students described experiences.',status='PARTIALLY_SUPPORTED',qualifier='in these interviews',supporting_sources=[source.id],supporting_evidence=['evd_original'])
    evidence = Evidence(id='evd_original',claim_id=claim.id,source_id=source.id,evidence_text=quote,extraction_method='VERBATIM_ABSTRACT',location={'locator':'abstract'})
    calls = []
    def retrieval(self,request):
        calls.append(1)
        return RetrievalAgentResponse(sources=request.sources,parsed_text_by_source={source.id:quote})
    monkeypatch.setattr('src.agents.research.RetrievalAgent.execute',retrieval)
    request = DeepResearchRequest(project=project,user_request='Synthetic interviews',sources=[source],claims=[claim],evidence=[evidence],generate_docx=False)
    first = DeepResearchWorkflow().execute(request)
    assert first.success
    before = {p.name:p.read_bytes() for p in directory.iterdir() if p.is_file()}
    run_before = {str(p.relative_to(directory)):p.read_bytes() for p in (directory/'runs').rglob('*') if p.is_file()}
    revised_claim = claim.model_copy(update={'claim_text':'Students described interview experiences.'})
    bad_evidence = evidence.model_copy(update={'evidence_text':'Different unreviewed text with the old ID.'})
    bad = DeepResearchWorkflow().execute(request.model_copy(update={'claims':[revised_claim],'evidence':[bad_evidence], 'search_options':{'concepts':['changed']}}))
    assert not bad.success and 'new evidence ID' in bad.error_message
    assert calls == [1]
    assert {p.name:p.read_bytes() for p in directory.iterdir() if p.is_file()} == before
    assert {str(p.relative_to(directory)):p.read_bytes() for p in (directory/'runs').rglob('*') if p.is_file()} == run_before
    revised_evidence = evidence.model_copy(update={'id':'evd_revision'})
    revised_claim.supporting_evidence = [revised_evidence.id]
    revised = DeepResearchWorkflow().execute(request.model_copy(update={'claims':[revised_claim],'evidence':[revised_evidence]}))
    assert revised.success and revised.run_id != first.run_id
    assert len((directory/'evidence.jsonl').read_text().splitlines()) == 2
    assert json.loads((directory/'current_evidence.json').read_text())[0]['id'] == 'evd_revision'
    assert json.loads((directory/'claims.json').read_text())[0]['supporting_evidence'] == ['evd_revision']
    assert all((directory/name).read_bytes() == content for name,content in run_before.items())


@pytest.mark.parametrize('budget',[1,2])
def test_discovery_does_not_reach_target_with_unmatched_concepts(budget):
    class Provider:
        def __init__(self,name,title): self.name,self.title,self.calls = name,title,0
        def execute(self,request):
            self.calls += 1
            return ResearchResponse(results=[Source(title=f'{self.title} {i}',authors=['A'],year=2024) for i in range(25)])
    first = Provider('partial-concept','Academic burnout')
    second = Provider('both-concepts','Academic burnout and perfectionistic concerns')
    result = DiscoveryAgent().execute(DiscoveryRequest(queries=['burnout and perfectionism'],concepts=['academic burnout','perfectionistic concerns'],
        providers=[first,second],target_sources=10,request_budget=budget))
    assert first.calls == 1 and second.calls == budget-1
    assert len(result.raw_sources) == budget*25
    assert result.metadata['stop_reason'] == ('target_reached' if budget==2 else 'request_budget_exhausted')
    assert result.metadata['target_candidate_count'] == (25 if budget==2 else 0)
    assert result.metadata['target_criteria'] == 'all_structured_concepts'
    if budget==2: assert 'perfectionistic concerns' in result.sources[0].title.lower()


def test_quantitative_discovery_defaults_to_at_least_forty_candidates(tmp_path,monkeypatch):
    from src.workflows.deep_research import DeepResearchWorkflow,DeepResearchRequest
    directory=tmp_path/'project';directory.mkdir()
    project=Project(name='target-check',workspace='test',path=str(directory))
    captured=[]
    class Provider:
        name='synthetic'
    def capture(self,request):
        captured.append(request.target_sources)
        raise RuntimeError('Stop after capturing the discovery request')
    monkeypatch.setattr(DiscoveryAgent,'execute',capture)
    result=DeepResearchWorkflow().execute(DeepResearchRequest(project=project,user_request='Synthetic quantitative review',providers=[Provider()],quantitative_review=True))
    assert not result.success and captured == [40]
    assert not list(directory.glob('*.json'))


def test_ambiguous_aliases_cannot_add_an_independent_publication():
    records = [Source(id=sid,title='Same title',authors=['A'],year=2024,doi=doi,provider=sid,provider_record_id=sid)
        for sid,doi in [('a','10.1234/a'),('unknown-one',None),('b','10.1234/b'),('unknown-two',None)]]
    identities = {}
    assert len(deduplicate(records,identities=identities)) == 3
    assert identities == {'a':'doi:10.1234/a','b':'doi:10.1234/b','unknown-one':None,'unknown-two':None}
