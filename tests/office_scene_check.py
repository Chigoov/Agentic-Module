"""Browser check: python tests/office_scene_check.py --output <screenshot-folder>.

Uses page-local API responses, never submits Hermes tasks or writes job history.
Requires the already-installed Playwright and the local monitor on port 8000.
"""
import argparse
import json
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    folder = args.output or Path(tempfile.mkdtemp(prefix='office-scene-'))
    folder.mkdir(parents=True, exist_ok=True)
    state = {'finished': False, 'offline': False, 'activities': ['model', 'search', 'code', 'test'], 'checks': [], 'new_turn': False}
    errors = []
    checks = []
    base = 'http://127.0.0.1:8000'

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for view, profile in [('bengkel', 'bengkel'), ('riset', 'asistenriset'), ('', 'bengkel')]:
            state['finished'] = True
            page = browser.new_page(viewport={'width': 1440, 'height': 1100})
            page.on('pageerror', lambda error: errors.append(str(error)))
            job_id = f'hermes:{profile}:visual-check'

            def respond(route):
                if state['offline']:
                    route.abort()
                    return
                status = 'completed' if state['finished'] else 'running'
                common = dict(job_id=job_id, profile=profile, source='hermes',
                              time='2026-10-10T12:00:00Z', project_name='Simulasi pemeriksaan visual')
                agents = [dict(common, seq=i+1, event_kind='agent', agent_id=f'check-{i}',
                               stage='hermes_model' if i == 0 else 'hermes_tool',
                               tool_name=None if i == 0 else 'terminal', outcome='passed' if state['finished'] else None,
                               activity=activity, visual_role=i, status=status)
                          for i, activity in enumerate(state['activities'])]
                events = [dict(common, seq=0, event_kind='job', agent_id='coordinator',
                               stage='hermes_turn', status='running'), *agents,
                          *[dict(common, **check) for check in state['checks']]]
                if state['finished']:
                    events.append(dict(common, seq=5, event_kind='job', agent_id='coordinator',
                                       stage='hermes_turn', status='completed'))
                if state['new_turn']:
                    events.append(dict(common, seq=100, event_kind='job', agent_id='coordinator',stage='hermes_turn',status='running'))
                hermes = {'connected': True, 'revision': 1}
                if '/api/jobs' in route.request.url:
                    payload = {'hermes': hermes, 'jobs': [dict(common, title=common['project_name'],
                               status=status, agents=agents)], 'counts': {'running': int(not state['finished']),
                               'review': 0, 'agents': 0 if state['finished'] else 4}}
                elif '/api/progress' in route.request.url:
                    payload = {'hermes': hermes, 'events': events}
                else:
                    route.fulfill(content_type='text/event-stream', body=': browser check\n\n')
                    return
                route.fulfill(content_type='application/json', body=json.dumps(payload))

            page.route('**/api/*', respond)
            url = base + '/' + view + (f'?session_id=visual-check' if view else '')
            page.goto(url, wait_until='domcontentloaded')
            page.wait_for_function("document.querySelector('[data-value=connection]').textContent.includes('Terhubung')")
            assert page.locator('.actor.idle').count() == 4
            assert page.locator('.actor').evaluate_all('(items)=>items.every(e=>!e.getAnimations().some(a=>a instanceof CSSTransition))')
            state['finished'] = False
            page.wait_for_function("document.querySelectorAll('.actor.working').length===4")
            page.evaluate("async()=>{await Promise.all([...new Set([...document.querySelectorAll('.sprite')].map(e=>getComputedStyle(e,'::before').backgroundImage.slice(5,-2)))].map(src=>new Promise((resolve,reject)=>{const img=new Image();img.onload=resolve;img.onerror=reject;img.src=src})));}")
            assert page.locator('.furniture').count() == 4
            assert page.locator('.actor.walking').count() == 0
            positions = page.locator('.actor.working .sprite').evaluate_all('(items)=>items.map(e=>getComputedStyle(e).backgroundPosition)')
            assert positions == ['0% 0%', '100% 0%', '0% 100%', '100% 100%'], positions
            assert page.locator('.actor.working').evaluate_all('(items)=>items.every(e=>getComputedStyle(e).transitionDuration==="0s")')
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e).animationName==="none")')
            before = page.locator('.sprite').first.evaluate('(e)=>e.getAnimations().length')
            page.locator('.actor').first.click()
            assert page.locator('.sprite').first.evaluate('(e)=>e.getAnimations().length') == before
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e,"::after").animationName==="aai-head")')
            page.locator('.world').screenshot(path=str(folder / (f'{view or "beranda"}-working.png')))

            state['activities'][3] = 'build'
            page.wait_for_function("document.querySelectorAll('.actor')[3].dataset.activity==='build'")
            assert page.locator('.actor').nth(3).locator('.work-prop').evaluate('(e)=>getComputedStyle(e).animationName') == 'aai-build'
            page.get_by_label('Gerakan', exact=True).uncheck()
            assert page.locator('.work-prop').evaluate_all('(items)=>items.every(e=>getComputedStyle(e).animationName==="none")')
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e,"::after").animationName==="none")')
            page.get_by_label('Gerakan', exact=True).check()
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.work-prop').evaluate_all('(items)=>items.every(e=>getComputedStyle(e).animationName==="none")')
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e,"::after").animationName==="none")')
            page.emulate_media(reduced_motion='no-preference')

            positions_before = page.locator('.actor').evaluate_all('(items)=>items.map(e=>[e.style.left,e.style.top])')
            state['offline'] = True
            page.wait_for_function("document.querySelectorAll('.actor.offline').length===4")
            assert page.locator('.actor.working').count() == 4  # Freeze last seated pose; do not invent idle motion.
            assert page.locator('.actor').evaluate_all('(items)=>items.map(e=>[e.style.left,e.style.top])') == positions_before
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e,"::after").animationName==="none")')
            state['offline'] = False
            page.wait_for_function("document.querySelectorAll('.actor.offline').length===0")
            assert page.locator('.actor.working').count() == 4
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('.world').screenshot(path=str(folder / (f'{view or "beranda"}-working-mobile.png')))
            page.set_viewport_size({'width': 1440, 'height': 1100})

            if view == 'bengkel':
                state['checks'] = [dict(seq=10+i, event_kind='agent', agent_id=f'check-result-{i}',
                                       stage='hermes_tool', tool_name='terminal', activity='test' if i<2 else 'build',
                                       visual_role=3, status='failed' if i==1 else 'completed', outcome=outcome)
                                   for i, outcome in enumerate(['passed', 'failed', 'unconfirmed'])]
                state['checks'].append(dict(state['checks'][0], seq=14))  # Duplicate notification is one operation.
                page.wait_for_function("document.querySelector('[data-value=read]').textContent==='1/3'")
                page.get_by_role('button', name='1/3 Lihat rincian').click()
                assert page.locator('.check-panel').get_attribute('open') is not None
                assert page.locator('.check-row').count() == 4  # Includes currently running build, outside denominator.
                assert '1 berhasil · 1 gagal · 1 belum terkonfirmasi · 1 berjalan' in page.locator('.check-panel summary').inner_text()
                for outcome in ['passed', 'failed', 'unconfirmed', 'running']:
                    page.get_by_label('Filter hasil tes dan build').select_option(outcome)
                    assert page.locator('.check-row').count() == 1
                    assert page.locator('.check-row').get_attribute('data-outcome') == outcome
                    assert page.locator('.check-panel').get_attribute('open') is not None
                page.get_by_label('Filter hasil tes dan build').select_option('all')
                page.locator('.check-panel').screenshot(path=str(folder/'checks-list-simulation.png'))
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('.check-panel').screenshot(path=str(folder/'checks-list-mobile.png'))
                page.set_viewport_size({'width':1440,'height':1100})
                state['checks'].extend([
                    dict(seq=15,event_kind='agent',agent_id='repair-check',stage='hermes_tool',tool_name='patch',activity='code',visual_role=2,status='completed'),
                    dict(seq=16,event_kind='agent',agent_id='retry-check',stage='hermes_tool',tool_name='terminal',activity='test',visual_role=3,status='completed',outcome='passed')])
                page.wait_for_function("document.querySelector('[data-value=read]').textContent==='2/4'")
                assert page.locator('.workflow-step').count() == 7  # search, code, build, test, build, code, test
                assert page.locator('.workflow-step[data-step=check-result-0]').get_attribute('data-status') == 'failed'
                page.locator('.workflow-step[data-step=retry-check]').click()
                assert 'Berhasil' in page.locator('.workflow-detail').inner_text()
                assert page.locator('.workflow-operations li').count() == 1
                page.get_by_role('button',name='Langkah terbaru',exact=True).click()
                assert page.locator('.workflow-step[data-step=retry-check]').get_attribute('aria-pressed') == 'true'
                page.locator('.live-workflow').screenshot(path=str(folder/'workflow-simulation.png'))
                state['new_turn'] = True
                page.wait_for_function("document.querySelectorAll('.workflow-step').length===0")
                assert 'Menunggu operasi pertama' in page.locator('.workflow-track').inner_text()
                assert page.locator('[data-value=read]').inner_text() == '—'
                state['new_turn'] = False
                state['checks'] = []
                page.wait_for_function("document.querySelectorAll('.check-row').length===1")
                page.get_by_role('button', name='Lihat rincian').click()
            else:
                assert page.locator('.check-panel').count() == 0
                assert page.locator('.live-workflow').count() == (1 if view=='riset' else 0)

            state['finished'] = True
            page.wait_for_function("document.querySelectorAll('.actor.idle').length===4")
            assert page.locator('.actor').count() == 4
            assert page.locator('.actor.working').count() == 0
            assert page.locator('.sprite').evaluate_all('(items)=>items.every(e=>getComputedStyle(e).backgroundImage.includes("chibi-v4"))')
            page.wait_for_function("document.querySelectorAll('.actor.walking').length>0", timeout=7000)
            assert page.locator('.actor.walking.working').count() == 0
            page.get_by_label('Gerakan', exact=True).uncheck()
            page.locator('.world').screenshot(path=str(folder / (f'{view or "beranda"}-idle.png')))
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(folder / (f'{view or "beranda"}-mobile.png')), full_page=True)
            assert page.locator('.actor').evaluate_all('(items)=>items.every(e=>{const a=e.getBoundingClientRect(),w=e.closest(".world").getBoundingClientRect();return a.left>=w.left&&a.right<=w.right&&a.top>=w.top&&a.bottom<=w.bottom})')
            checks.append({'view': view or 'beranda', 'four_seated_poses': True, 'furniture_depth': True,
                           'chairs_do_not_slide': True, 'idle_visible_and_moving': True,
                           'motion_controls': True, 'offline_freezes_pose': True, 'mobile_no_overflow': True,
                           'check_list_counts_filters_and_dedup': view == 'bengkel'})
            page.close()
            state['activities'][3] = 'test'
        assert not errors, errors
        browser.close()
    result = {'passed': True, 'data_source': 'page-local simulation', 'checks': checks, 'console_errors': errors}
    (folder / 'scene-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
