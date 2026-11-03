"""Local projection checks; fixtures are never written to the real office history."""
import json
from src.runtime.hermes_monitor import HermesMonitor, tool_role
from src.runtime import monitor
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen


def test_native_lifecycle_dedup_privacy_parallel_and_restart(tmp_path):
    observer = HermesMonitor(tmp_path)
    observer.connected = True
    observer.epoch = 'backend-1'
    observer.metadata = {'live': {'profile': 'default', 'stored': 'stored-1'}, 'other': {'profile': 'asistenriset', 'stored': 'stored-2'}}
    def event(seq, kind, data=None, sid='live'):
        observer.consume({'session_id': sid, 'seq': seq, 'type': kind, 'payload': data or {}})
    event(1, 'message.start')
    event(2, 'tool.start', {'tool_id': 'a', 'name': 'search_files', 'args': {'secret': 'PRIVATE'}})
    event(3, 'tool.start', {'tool_id': 'b', 'name': 'read_file', 'args': {'path': 'PRIVATE'}})
    event(3, 'tool.start', {'tool_id': 'b', 'name': 'read_file', 'args': {'path': 'PRIVATE'}})
    assert len(observer.events) == 6
    job = observer.snapshot()['jobs'][0]
    assert len([a for a in job['agents'] if a['status'] == 'running']) == 2
    assert {a['visual_role'] for a in job['agents'] if a['status'] == 'running'} == {1, 2}
    event(4, 'tool.complete', {'tool_id': 'a', 'name': 'search_files', 'result': {'error': 'PRIVATE'}})
    event(5, 'message.delta', {'text': 'PRIVATE'})
    event(6, 'reasoning.delta', {'text': 'PRIVATE'})
    event(7, 'message.complete', {'status': 'interrupted', 'text': 'PRIVATE'})
    event(1, 'message.start', sid='other')
    assert {j['status'] for j in observer.snapshot()['jobs']} == {'running', 'cancelled'}
    event(8, 'message.start')
    event(7, 'message.complete', {'status': 'interrupted'})  # Late replay cannot cancel the new turn.
    assert next(j for j in observer.snapshot()['jobs'] if j['profile'] == 'default')['status'] == 'running'
    assert len(next(j for j in observer.snapshot()['jobs'] if j['profile'] == 'default')['agents']) == 1
    event(9, 'message.complete', {'status': 'error'})
    assert next(j for j in observer.snapshot()['jobs'] if j['profile'] == 'default')['status'] == 'failed'
    event(10, 'message.start')
    event(11, 'approval.request')
    assert next(j for j in observer.snapshot()['jobs'] if j['profile'] == 'default')['status'] == 'pending'
    event(12, 'tool.complete', {'name': 'clarify', 'tool_id': 'c', 'result': {'success': True}})
    assert next(j for j in observer.snapshot()['jobs'] if j['profile'] == 'default')['status'] == 'running'
    event(13, 'message.complete', {'status': 'complete'})
    assert 'PRIVATE' not in observer.path.read_text(encoding='utf-8')
    restored = HermesMonitor(tmp_path)
    assert len(restored.events) == len(observer.events)
    assert any(j['status'] == 'unknown' for j in restored.snapshot()['jobs'])
    restored.epoch, restored.metadata = observer.epoch, observer.metadata
    restored.consume({'session_id': 'live', 'seq': 13, 'type': 'message.complete', 'payload': {'status': 'complete'}})
    assert len(restored.events) == len(observer.events)


def test_linked_aai_job_and_disconnect_projection(tmp_path, monkeypatch):
    observer = HermesMonitor(tmp_path)
    observer.connected, observer.epoch = True, 'backend'
    observer.metadata['live'] = {'profile': 'default', 'stored': 'stored'}
    observer.consume({'session_id': 'live', 'seq': 1, 'type': 'message.start'})
    identifier = 'a' * 32
    observer.consume({'session_id': 'live', 'seq': 2, 'type': 'tool.complete', 'payload': {
        'name': 'terminal', 'tool_id': 'one', 'args': {'command': 'python aai_read_pdf.py input.pdf'},
        'result': {'output': json.dumps({'job_id': identifier})}}})
    assert observer.snapshot()['jobs'][0]['linked_job_ids'] == [identifier]
    monkeypatch.setattr(monitor, '_hermes', observer)
    monkeypatch.setattr(monitor, 'read_progress', lambda **_: [])
    assert monitor._jobs()['counts']['running'] == 1
    observer.connected = False
    assert monitor._jobs()['counts']['running'] == 0
    assert monitor._jobs()['counts']['agents'] == 0
    assert monitor._monitor_events()[-1]['status'] == 'unknown'
    assert tool_role('terminal', {'command': 'Get-ChildItem input'}) == 1
    assert tool_role('terminal', {'command': 'python aai_read_pdf.py input.pdf'}) == 2
    observer.metadata['live']['profile'] = 'asistenriset'
    observer.consume({'session_id': 'live', 'seq': 3, 'type': 'message.start'})
    assert len(observer.snapshot()['jobs']) == 1
    assert observer.snapshot()['jobs'][0]['profile'] == 'asistenriset'
    assert len(observer.events_for('hermes:asistenriset:stored')) == len(observer.events)
    assert '"profile": "default"' in observer.path.read_text(encoding='utf-8')  # Historical log stays append-only.


def test_bengkel_activity_task_scope_and_profile_routes(tmp_path, monkeypatch):
    observer = HermesMonitor(tmp_path)
    observer.connected, observer.epoch = True, 'backend'
    observer.metadata = {p: {'profile': p, 'stored': p + '-session'} for p in ('bengkel', 'asistenriset')}
    def emit(seq, kind, data=None, profile='bengkel'):
        observer.consume({'session_id': profile, 'seq': seq, 'type': kind, 'payload': data or {}})
    emit(1, 'message.start')
    for seq, name, args, activity, role in [(2,'read_file',{'path':'PRIVATE.py'},'read',1),
        (4,'write_file',{'path':'PRIVATE.py'},'code',2),
        (6,'terminal',{'command':'dotnet test --no-build PRIVATE'},'test',3),
        (8,'terminal',{'command':'dotnet build PRIVATE'},'build',3)]:
        emit(seq, 'tool.start', {'name': name, 'tool_id': str(seq), 'args': args})
        emit(seq+1, 'tool.complete', {'name': name, 'tool_id': str(seq), 'result': json.dumps({'exit_code': 1 if activity == 'test' else 0})})
        row = observer.events[-2]
        assert (row['activity'], row['visual_role']) == (activity, role)
        assert row['status'] == ('failed' if activity == 'test' else 'completed')
        assert row['outcome'] == ('failed' if activity == 'test' else 'passed')
    emit(10, 'message.complete')
    emit(11, 'message.start')
    emit(1, 'message.start', profile='asistenriset')
    assert {e['turn_seq'] for e in observer.events_for('hermes:bengkel:bengkel-session')} == {1,11}
    assert 'PRIVATE' not in observer.path.read_text(encoding='utf-8')
    monkeypatch.setattr(monitor, '_hermes', observer)
    monkeypatch.setattr(monitor, 'read_progress', lambda **_: [])
    monkeypatch.setattr(monitor, '_aai_jobs', lambda *_: [])
    assert monitor._jobs()['counts']['running'] == 2
    assert monitor._jobs('bengkel')['counts']['running'] == 1
    assert {e['profile'] for e in monitor._monitor_events(profile='asistenriset')} == {'asistenriset'}
    server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.create_handler())
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        with urlopen(base+'/api/progress?profile=bengkel') as response:
            assert {e['profile'] for e in json.load(response)['events']} == {'bengkel'}
        for route, view in [('/', 'home'),('/riset','research'),('/bengkel','bengkel'),('/?job_id=hermes:bengkel:bengkel-session','bengkel')]:
            with urlopen(base+route) as response:
                assert f'data-view="{view}"' in response.read().decode()
    finally:
        server.shutdown(); thread.join(timeout=5); server.server_close()


def test_selected_workflow_retains_long_history(tmp_path, monkeypatch):
    observer = HermesMonitor(tmp_path)
    observer.connected, observer.epoch = True, 'backend'
    observer.metadata['live'] = {'profile': 'bengkel', 'stored': 'long-session'}
    observer.consume({'session_id': 'live', 'seq': 1, 'type': 'message.start'})
    for seq in range(2, 1003):
        observer._record('live', seq, 'hermes_tool_patch', 'completed', agent=str(seq), tool='patch', activity='code')
    job_id = 'hermes:bengkel:long-session'
    monkeypatch.setattr(monitor, '_hermes', observer)
    aai_events = [{'job_id': 'aai-long', 'time': str(i), 'stage': 'writing'} for i in range(1003)]
    monkeypatch.setattr(monitor, 'read_progress', lambda **kw: aai_events if kw['limit'] is None else aai_events[-kw['limit']:])
    selected = monitor._monitor_events(job_id, 'bengkel')
    assert len(selected) == 1003
    assert selected[0]['stage'] == 'hermes_turn'
    assert {e['turn_seq'] for e in selected} == {1}
    assert len(observer.events_for()) == len(monitor._monitor_events()) == 1000
    assert len(monitor._monitor_events('aai-long', 'asistenriset')) == 1003
