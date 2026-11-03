"""Read-only observer of the existing Hermes Desktop JSON-RPC event stream."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from threading import Event, RLock, Thread
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def tool_activity(name: str, args: dict) -> str:
    # Classify locally; command arguments and result bodies never enter the office log.
    action = (name + ' ' + str(args.get('command', ''))).lower()
    if name in {'clarify', 'ask_user'}: return 'waiting'
    if re.search(r'pytest|unittest|\bdotnet test\b|\btests?\b|regression|\bassert\b|\bcheck\b', action): return 'test'
    if re.search(r'\b(build|publish|compile|msbuild|compileall|py_compile)\b', action): return 'build'
    if re.search(r'audit|verif|review|\bgit diff\b', action): return 'review'
    if name == 'patch' or re.search(r'write_file|edit_file|apply_patch|replace|set-content', action):
        return 'report' if Path(str(args.get('path', ''))).suffix.lower() in {'.md', '.txt', '.docx'} else 'code'
    if re.search(r'search|find_file|get-childitem|\brg\b|glob|list_directory|\bgit status\b', action): return 'search'
    if re.search(r'read|extract|pdf|get-content|\bcat\b', action): return 'read'
    return 'execute'


def tool_role(name: str, args: dict, profile: str = '') -> int:
    activity = tool_activity(name, args)
    if profile == 'bengkel':
        return {'search': 1, 'read': 1, 'code': 2, 'test': 3, 'build': 3, 'review': 3}.get(activity, 0)
    return {'test': 3, 'build': 3, 'review': 3, 'search': 1, 'read': 2}.get(activity, 0)


class HermesMonitor:
    def __init__(self, directory: Path, home: Path | None = None):
        self.home = home or Path.home() / '.hermes'
        self.path = directory / 'hermes-events.jsonl'
        self.lock = RLock()
        self.stop = Event()
        self.connected = False
        self.error = 'Hermes belum tersambung'
        self.epoch = ''
        self.metadata = {}
        self.events = []
        self.seen = set()
        self.latest_seq = {}
        self.revision = 0
        if self.path.is_file():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                try: row = json.loads(line)
                except ValueError: continue
                self.events.append(row)
                self.seen.add(row['event_id'])
                key = (row['event_id'].split(':', 1)[0], row['runtime_session_id'])
                self.latest_seq[key] = max(self.latest_seq.get(key, -1), row['seq'])
            self.revision = max((e.get('revision', i+1) for i,e in enumerate(self.events)), default=0)

    def start(self):
        Thread(target=self._run, name='hermes-office-observer', daemon=True).start()

    def _record(self, sid, seq, stage, status, *, kind='agent', agent='model', role=0, tool='', linked_job='', activity='', outcome=''):
        meta = self.metadata[sid]
        identifier = f'{self.epoch}:{sid}:{seq}:{stage}:{status}'
        with self.lock:
            if identifier in self.seen: return
            row = {'event_id': identifier, 'time': datetime.now(UTC).isoformat(),
                   'revision': self.revision + 1,
                   'source': 'hermes', 'job_id': f"hermes:{meta['profile']}:{meta['stored']}",
                   'session_id': meta['stored'], 'runtime_session_id': sid, 'profile': meta['profile'],
                   'project_name': f"Hermes · {meta['profile']} · {meta['stored']}",
                   'stage': stage, 'status': status, 'event_kind': kind,
                   'agent_id': agent, 'visual_role': role, 'tool_name': tool, 'seq': seq,
                   'message': tool or {'hermes_model': 'Menyiapkan jawaban', 'hermes_answer': 'Menulis jawaban',
                                      'hermes_turn': 'Aktivitas chat Hermes'}.get(stage, stage)}
            if linked_job: row['linked_job_id'] = linked_job
            if activity: row['activity'] = activity
            if outcome: row['outcome'] = outcome
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            self.events.append(row)
            self.seen.add(identifier)
            self.revision += 1

    def consume(self, frame):
        sid, kind = frame.get('session_id'), frame.get('type')
        if sid not in self.metadata: return
        seq = frame.get('seq')
        if not isinstance(seq, int) or seq < 0: return
        data = frame.get('payload') or {}
        if not isinstance(data, dict): return
        if kind not in {'message.start', 'tool.start', 'tool.complete', 'message.delta', 'message.complete', 'approval.request'}: return
        key = (self.epoch, sid)
        if seq < self.latest_seq.get(key, -1): return
        self.latest_seq[key] = seq
        if kind in {'tool.start', 'tool.complete', 'message.delta'}:
            job = next((j for j in self.snapshot()['jobs'] if j['session_id'] == self.metadata[sid]['stored']), None)
            if job and job['status'] in {'pending', 'unknown'}:
                self._record(sid, seq, 'hermes_resume', 'running', kind='job', agent='')
        if kind == 'message.start':
            self._record(sid, seq, 'hermes_turn', 'running', kind='job', agent='')
            self._record(sid, seq, 'hermes_model', 'running')
        elif kind == 'tool.start':
            name = str(data.get('name') or 'tool')[:100]
            args = data.get('args') if isinstance(data.get('args'), dict) else {}
            self._record(sid, seq, 'hermes_model', 'completed')
            self._record(sid, seq, 'hermes_tool_' + name, 'running', agent=str(data.get('tool_id') or seq),
                         role=tool_role(name, args, self.metadata[sid]['profile']), tool=name, activity=tool_activity(name, args))
        elif kind == 'tool.complete':
            name = str(data.get('name') or 'tool')[:100]
            result = data.get('result')
            if isinstance(result, str):
                try: result = json.loads(result)
                except ValueError: pass
            failed = isinstance(result, dict) and (result.get('is_error') is True or result.get('success') is False or bool(result.get('error')) or isinstance(result.get('exit_code'), int) and result['exit_code'] != 0)
            args = data.get('args') if isinstance(data.get('args'), dict) else {}
            prior = next((e for e in reversed(self.events) if e['runtime_session_id'] == sid and e['agent_id'] == str(data.get('tool_id') or seq)), {})
            activity = prior.get('activity') or tool_activity(name, args)
            outcome = 'failed' if failed else 'passed' if isinstance(result, dict) and result.get('exit_code') == 0 else 'unconfirmed'
            linked = ''
            if 'aai_read_pdf.py' in str(args.get('command', '')):
                # Only the known AAI helper's returned identifier is retained, never its raw output.
                output = result if isinstance(result, str) else str(result.get('output') or json.dumps(result)) if isinstance(result, dict) else ''
                match = re.search(r'"job_id"\s*:\s*"([0-9a-f]{32})"', output)
                if match: linked = match[1]
            self._record(sid, seq, 'hermes_tool_' + name, 'failed' if failed else 'completed',
                         agent=str(data.get('tool_id') or seq), role=prior.get('visual_role', tool_role(name, args, self.metadata[sid]['profile'])), tool=name, linked_job=linked, activity=activity, outcome=outcome)
            self._record(sid, seq, 'hermes_model', 'running')
        elif kind == 'message.delta':
            # Record the observed streaming state once, never response/reasoning text.
            if self._agent_state(sid, 'model') != ('hermes_answer', 'running'):
                self._record(sid, seq, 'hermes_answer', 'running')
        elif kind == 'message.complete':
            status = {'error': 'failed', 'interrupted': 'cancelled'}.get(data.get('status'), 'completed')
            if data.get('partial'): status = 'partial'
            phase = 'hermes_answer' if self._agent_state(sid, 'model') == ('hermes_answer', 'running') else 'hermes_model'
            self._record(sid, seq, phase, status)
            self._record(sid, seq, 'hermes_turn', status, kind='job', agent='')
        elif kind == 'approval.request':
            self._record(sid, seq, 'hermes_turn', 'pending', kind='job', agent='')

    def _agent_state(self, sid, agent):
        with self.lock:
            row = next((e for e in reversed(self.events) if e['runtime_session_id'] == sid and e['agent_id'] == agent), None)
        return (row['stage'], row['status']) if row else None

    def snapshot(self):
        with self.lock:
            jobs = {}
            # ponytail: reuse a small append-only history; index by session if this becomes large.
            rows = self._project_events()
            for row in rows:
                job = jobs.setdefault(row['job_id'], {'job_id': row['job_id'], 'title': row['project_name'],
                    'source': 'hermes', 'session_id': row['session_id'], 'profile': row['profile'],
                    'status': 'idle', 'agents': {}, 'time': row['time'], 'latest': row})
                job.update(time=row['time'], latest=row)
                if row.get('linked_job_id'): job.setdefault('linked_job_ids', set()).add(row['linked_job_id'])
                if row['event_kind'] == 'job':
                    if row['stage'] == 'hermes_turn' and row['status'] == 'running': job['agents'] = {}
                    job['status'] = row['status']
                else: job['agents'][row['agent_id']] = row
            for job in jobs.values():
                if not self.connected and job['status'] in {'running', 'pending'}: job['status'] = 'unknown'
                job['agents'] = list(job['agents'].values())
                job['linked_job_ids'] = sorted(job.get('linked_job_ids', []))
            return {'connected': self.connected, 'status': self.error, 'revision': self.revision,
                    'jobs': sorted(jobs.values(), key=lambda j:j['time'], reverse=True), 'events': rows[-1000:]}

    def _project_events(self):
        # Correct earlier lazy-profile observations using the latest authoritative identity; never rewrite the journal.
        fields = ('profile', 'job_id', 'project_name')
        identities = {(e['runtime_session_id'], e['session_id']): e for e in self.events}
        turns, rows = {}, []
        for e in self.events:
            key = (e['runtime_session_id'], e['session_id'])
            if e['stage'] == 'hermes_turn' and e['status'] == 'running' and e['seq'] >= 0:
                turns[key] = e['seq']
            row = {**e, **{k:identities[key][k] for k in fields}, 'turn_seq': turns.get(key, 0)}
            if row.get('tool_name') and not row.get('activity'):
                # Older safe logs retain tool names but no arguments: never infer a terminal command.
                row['activity'] = tool_activity(row['tool_name'], {})
                row['visual_role'] = tool_role(row['tool_name'], {}, row['profile'])
            rows.append(row)
        return rows

    def events_for(self, job_id=None, profile=None):
        with self.lock:
            rows = [e for e in self._project_events() if (job_id is None or e['job_id'] == job_id) and (profile is None or e['profile'] == profile)]
            return rows if job_id else rows[-1000:]

    def _endpoint(self):
        ledger = json.loads((self.home / 'spawn-ledger.json').read_text(encoding='utf-8'))
        for row in reversed(ledger):
            port = row.get('port')
            if row.get('purpose') not in {'serve', 'dashboard'} or row.get('host') not in {'127.0.0.1', 'localhost', '::1'}: continue
            if not isinstance(port, int) or not 1 <= port <= 65535: continue
            base = f'http://127.0.0.1:{port}'
            try:
                with urlopen(base + '/', timeout=3) as response: html = response.read(2_000_000).decode('utf-8')
                match = re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*("(?:\\.|[^"\\])*")', html)
                if match: return base, json.loads(match[1])
            except (OSError, ValueError): continue
        raise OSError('Hermes Desktop belum tersedia')

    def _run(self):
        try:
            from websockets.sync.client import connect
        except ImportError:
            self.error = 'Runtime monitor belum memiliki websockets'; return
        while not self.stop.is_set():
            try:
                base, token = self._endpoint()
                with connect(base.replace('http:', 'ws:') + '/api/ws?' + urlencode({'token': token}),
                             origin=base, open_timeout=4, max_size=8_000_000) as ws:
                    request_id, pending, attached, buffered = 0, {}, set(), []
                    def send(method, params, tag):
                        nonlocal request_id
                        request_id += 1
                        pending[request_id] = tag
                        ws.send(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}))
                    next_poll = 0
                    while not self.stop.is_set():
                        if time.monotonic() >= next_poll:
                            send('session.active_list', {}, ('list', None))
                            next_poll = time.monotonic() + 0.5
                        try: frame = json.loads(ws.recv(timeout=0.1))
                        except TimeoutError: continue
                        if frame.get('method') == 'event':
                            event = frame.get('params') or {}
                            if event.get('type') == 'gateway.ready':
                                self.epoch = str((event.get('payload') or {}).get('replay_epoch') or '')
                                self.connected, self.error = True, 'Hermes langsung tersambung'
                                self.revision += 1
                            elif event.get('type') in {'message.start', 'message.delta', 'message.complete', 'tool.start', 'tool.complete'}:
                                if event['type'] == 'message.delta': event = {k:event[k] for k in ('type', 'session_id', 'seq') if k in event}
                                if event.get('session_id') in attached: self.consume(event)
                                elif event.get('session_id'): buffered.append(event)
                            continue
                        if frame.get('method') in {'approval', 'clarify'}:
                            sid = (frame.get('params') or {}).get('session_id')
                            if sid in self.metadata:
                                self._record(sid, -self.revision-1, 'hermes_turn', 'pending', kind='job', agent='')
                            continue
                        tag = pending.pop(frame.get('id'), None)
                        if not tag or 'error' in frame: continue
                        result = frame.get('result') or {}
                        if tag[0] == 'list':
                            live = result.get('sessions', [])
                            disappeared = attached - {s.get('id') for s in live}
                            for sid in disappeared:
                                job = next((j for j in self.snapshot()['jobs'] if j['session_id'] == self.metadata[sid]['stored']), None)
                                if job and job['status'] in {'running', 'pending'}: self._record(sid, -self.revision, 'hermes_connection', 'unknown', kind='job', agent='')
                            for session in live:
                                sid = session.get('id')
                                if sid in attached:
                                    job = next((j for j in self.snapshot()['jobs'] if j['session_id'] == self.metadata[sid]['stored']), None)
                                    if job and job['status'] in {'running', 'pending'} and session.get('status') == 'idle':
                                        self._record(sid, -self.revision, 'hermes_connection', 'unknown', kind='job', agent='')
                                    elif job and job['status'] == 'unknown' and session.get('status') in {'working', 'streaming'}:
                                        self._record(sid, -self.revision, 'hermes_connection', 'running', kind='job', agent='')
                                if not isinstance(sid, str) or sid in attached or any(t == ('attach', sid) or t == ('replay', sid) for t in pending.values()): continue
                                if session.get('status') == 'idle': continue
                                send('session.activate', {'session_id': sid, 'omit_messages': True}, ('attach', sid))
                        elif tag[0] == 'attach':
                            sid = tag[1]
                            info = result.get('info') or {}
                            # A just-created lazy session has no owning profile yet; retry its snapshot after hydration.
                            if not info.get('profile_name'): continue
                            self.metadata[sid] = {'profile': str(info['profile_name'])[:80],
                                                  'stored': str(result.get('session_key') or sid)[:160], 'running': result.get('running')}
                            send('session.events.since', {'session_id': sid, 'last_seen': 0}, ('replay', sid))
                        elif tag[0] == 'replay':
                            sid = tag[1]
                            self.epoch = result.get('epoch') or self.epoch
                            replay = result.get('events', []) + [e for e in buffered if e.get('session_id') == sid]
                            buffered = [e for e in buffered if e.get('session_id') != sid]
                            for event in sorted(replay, key=lambda e:e.get('seq', 0)): self.consume(event)
                            attached.add(sid)
                            if any(r.get('method') in {'approval', 'clarify'} for r in result.get('open_requests', [])):
                                self._record(sid, -self.revision-1, 'hermes_turn', 'pending', kind='job', agent='')
                            # Snapshot recovery when a long turn's start has aged out of Hermes' replay ring.
                            if self.metadata[sid]['running'] and not any(e['runtime_session_id'] == sid and e['event_kind'] == 'job' for e in self.events):
                                self._record(sid, result.get('latest_seq', 0), 'hermes_turn', 'running', kind='job', agent='')
                                self._record(sid, result.get('latest_seq', 0), 'hermes_model', 'running')
            except Exception:
                with self.lock:
                    self.connected, self.error = False, 'Hermes terputus · mencoba menyambung kembali'
                    self.revision += 1
                # Never log credentials or payloads from transport exceptions.
                self.stop.wait(1)
