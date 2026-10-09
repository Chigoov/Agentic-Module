(() => {
  const root = document.getElementById('aai-studio-v2');
  const home = root.dataset.view === 'home';
  const get = name => root.querySelector(`[data-value="${name}"]`);
  const roles = [
    {name:'Arka',role:'Koordinator',short:'A',home:[43,35],rest:[64,54],idle:'Menikmati kopi'},
    {name:'Dinda',role:'Pencarian',short:'D',home:[27,49],rest:[27,56],idle:'Membaca buku'},
    {name:'Fajar',role:'Pembacaan',short:'F',home:[56,55],rest:[43,57],idle:'Peregangan ringan'},
    {name:'Salsa',role:'Reviewer',short:'S',home:[48,72],rest:[34,70],idle:'Bersantai sejenak'}
  ];
  const labels = {running:'Sedang bekerja',started:'Sedang bekerja',completed:'Selesai',success:'Selesai',partial:'Perlu ditinjau',pending:'Menunggu',blocked:'Terhambat',failed:'Gagal',idle:'Belum dijalankan'};
  const stages = {task_analysis:'Memahami tugas',planning:'Menyusun rencana',discovery:'Mencari sumber',deduplication:'Menghapus duplikat',ranking:'Memeringkat kandidat',verification:'Memeriksa metadata',access_check:'Memeriksa akses',retrieval:'Membaca dokumen',evidence_extraction:'Mengambil bukti',claim_verification:'Memeriksa klaim',human_review:'Menunggu tinjauan',synthesis:'Menyusun sintesis',writing:'Menulis',citation_audit:'Memeriksa sitasi',fact_audit:'Memeriksa fakta',docx_generation:'Membuat dokumen',task_analyzer_agent:'Analisis tugas',research_planner_agent:'Perencanaan',retrieval_agent:'Pembacaan dokumen',evidence_agent:'Ekstraksi bukti',academic_writing_workflow:'Alur penulisan',deep_research_workflow:'Alur riset',orchestrator_agent:'Koordinasi'};
  const active = s => ['running','started'].includes(s);
  const done = s => ['completed','success'].includes(s);
  const roleOf = e => {
    if(e.event_kind === 'job' && /workflow|orchestrator|integration_check|instruction/.test(e.stage || '')) return 0;
    const name = `${e.stage || ''} ${e.agent_id || ''}`;
    if(/audit|verification|review|conflict|claim/.test(name)) return 3;
    if(/retriev|evidence|reading|pdf/.test(name)) return 2;
    if(/discovery|search|deduplication|ranking/.test(name)) return 1;
    return 0;
  };
  Object.assign(stages, {instruction:'Tugas diterima',integration_check:'Pemeriksaan integrasi',citation_audit_agent:'Audit sitasi',fact_audit_agent:'Audit fakta',human_style_audit_agent:'Audit bahasa'});
  const title = e => stages[e.stage] || String(e.stage || 'Aktivitas').replaceAll('_',' ');
  const actors=[], cards=[], jobs=new Map();
  root.querySelector(`[data-nav="${home?'home':'research'}"]`).setAttribute('aria-current','page');
  let selectedRole=0, selectedJob=new URLSearchParams(location.search).get('job_id')||'', followLatest=!selectedJob, events=[], connected=false;
  const time = value => {const d=new Date(value);return Number.isNaN(+d)?'—':d.toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit',second:'2-digit'});};
  roles.forEach((role,i)=>{
    const actor=document.createElement('button');actor.type='button';actor.className='actor idle';
    actor.innerHTML=`<span class="sprite" aria-hidden="true" style="background-position-x:${i*100/3}%"></span><span class="nameplate waiting"><span class="dot"></span><span><strong>${role.name}</strong><span class="activity">${role.idle}</span></span></span>`;
    actor.style.left=role.home[0]+'%';actor.style.top=role.home[1]+'%';actor.style.zIndex=role.home[1];get('actors').append(actor);actors.push(actor);
    const card=document.createElement('button');card.type='button';card.className='agent';
    card.innerHTML=`<span class="portrait" aria-hidden="true" style="background-position-x:${i*100/3}%"></span><span class="agent-copy"><strong>${role.name}</strong><span class="role">${role.role}</span><span class="task"></span><span class="state"></span></span>`;
    const select=()=>{selectedRole=i;if(home)renderHome(homeData);else render();};
    actor.addEventListener('click',select);card.addEventListener('click',select);get('cards').append(card);cards.push(card);
  });
  function character(i,working,task){
    const role=roles[i],actor=actors[i],xy=working?role.home:role.rest;
    actor.classList.toggle('working',working);actor.classList.toggle('idle',!working);
    actor.classList.toggle('selected',selectedRole===i);actor.classList.toggle('offline',!connected);
    actor.querySelector('.nameplate').classList.toggle('waiting',!working);
    actor.querySelector('.activity').textContent=!connected?'Koneksi terputus':working?task:role.idle;
    actor.style.left=xy[0]+'%';actor.style.top=xy[1]+'%';actor.style.zIndex=Math.round(xy[1]);
    actor.setAttribute('aria-label',`${role.name}, ${role.role}: ${!connected?'koneksi terputus':working?task:role.idle}`);
    actor.setAttribute('aria-pressed',String(selectedRole===i));actor.dataset.state=!connected?'offline':working?'running':'idle';
    cards[i].setAttribute('aria-pressed',String(selectedRole===i));cards[i].dataset.state=actor.dataset.state;
    cards[i].querySelector('.task').textContent=working?task:role.idle;
    cards[i].querySelector('.state').textContent=!connected?'Koneksi terputus':working?'Sedang bekerja':'Siap menerima tugas';
  }
  function progress(scoped,jobEnd){
    // ponytail: show recorded stages, not a guessed percentage of an unknown workflow.
    const steps=new Map(),stageEvents=scoped.filter(e=>!e.event_kind);
    (stageEvents.length?stageEvents:scoped.filter(e=>e.event_kind==='agent')).forEach(e=>steps.set(e.stage,e));
    const recorded=[...steps.values()],finished=recorded.filter(e=>done(e.status)).length;
    const status=jobEnd?.status||scoped.at(-1)?.status||'idle';
    get('progress-status').textContent=labels[status]||status;get('progress-status').dataset.status=status;
    get('progress-title').textContent=scoped[0]?.project_name||'Belum ada pekerjaan dipilih';
    get('progress-caption').textContent=recorded.length?`${finished} dari ${recorded.length} tahap tercatat selesai`:'Tahapan akan muncul saat pekerjaan berjalan';
    get('progress-note').textContent=!connected?'Koneksi terputus · menampilkan catatan terakhir':jobEnd&&['partial','pending','blocked'].includes(status)?'Hasil menunggu pemeriksaan atau tindak lanjut':done(status)?'Operasi selesai · hasil tersedia untuk diperiksa':'Berdasarkan aktivitas yang tercatat';
    const track=get('progress-track');track.replaceChildren();
    const stageStatus=e=>jobEnd&&!active(jobEnd.status)&&active(e.status)?'pending':e.status;
    const stageLabel=e=>stageStatus(e)!==e.status?'Belum tercatat selesai':labels[e.status]||e.status;
    recorded.forEach(e=>{const step=document.createElement('span');step.className='progress-step';step.dataset.status=stageStatus(e);step.title=`${title(e)} · ${stageLabel(e)}`;step.setAttribute('aria-label',step.title);track.append(step);});
    const timeline=get('stage-list');timeline.replaceChildren();
    recorded.slice(-6).forEach(e=>{
      const row=document.createElement('div');row.className='stage-row';row.dataset.status=stageStatus(e);
      const marker=document.createElement('span');marker.className='stage-marker';marker.textContent=done(e.status)?'✓':e.status==='failed'?'!':'•';
      const copy=document.createElement('span');const name=document.createElement('strong');name.textContent=title(e);const state=document.createElement('small');state.textContent=stageLabel(e);copy.append(name,state);row.append(marker,copy);timeline.append(row);
    });
  }
  function render(){
    const scoped=events.filter(e=>e.job_id===selectedJob), latest=scoped.at(-1);
    const lifecycle=new Map(), roleEvents=roles.map(()=>[]);
    scoped.forEach(e=>{if(e.event_kind==='agent'||e.event_kind==='job')lifecycle.set(e.agent_id,e);roleEvents[roleOf(e)].push(e);});
    const jobEnd=[...scoped].reverse().find(e=>e.event_kind==='job');
    const terminal=jobEnd&&!active(jobEnd.status);
    const currentAgents=[...lifecycle.values()].filter(e=>active(e.status)&&!terminal);
    progress(scoped,jobEnd);
    get('workers').textContent=connected?String(currentAgents.length):'—';
    get('phase').textContent=latest?`${title(latest)} · ${labels[latest.status]||latest.status}`:'Menunggu pekerjaan';
    get('sequence').textContent=latest?`Aktivitas terakhir ${time(latest.time)}`:'Menunggu aktivitas';
    const candidates=[...scoped].reverse().find(e=>Number.isFinite(e.unique)||Number.isFinite(e.count));
    const retrieved=[...scoped].reverse().find(e=>Number.isFinite(e.retrieved));
    get('candidates').textContent=candidates?(candidates.unique??candidates.count):'—';
    get('read').textContent=retrieved?retrieved.retrieved:'—';
    get('blocked').textContent=jobEnd&&['partial','blocked','pending'].includes(jobEnd.status)?'Hasil masih memerlukan tinjauan.':jobEnd?.status==='failed'?'Pekerjaan gagal. Periksa catatan aktivitas.':'';
    roles.forEach((role,i)=>{
      const own=roleEvents[i], last=own.at(-1), working=connected&&!terminal&&(currentAgents.some(e=>roleOf(e)===i)||active(last?.status));
      character(i,working,last?title(last):role.idle);
    });
    const detail=roleEvents[selectedRole].at(-1);
    get('detail').textContent=`${roles[selectedRole].name} · ${roles[selectedRole].role} — `+(detail?(detail.message&&detail.message!==detail.stage?detail.message:title(detail)):'belum ada aktivitas pekerjaan tercatat.');
    const feed=get('events');feed.replaceChildren();
    scoped.slice(-8).reverse().forEach(e=>{
      const row=document.createElement('div');row.className='event';const initial=document.createElement('span');initial.className='initial';initial.textContent=roles[roleOf(e)].short;
      const copy=document.createElement('div');copy.className='event-copy';const heading=document.createElement('strong');heading.textContent=title(e);
      const msg=document.createElement('span');msg.textContent=e.message===e.stage?'':(e.message||'');
      const small=document.createElement('small');small.textContent=`${roles[roleOf(e)].name} · ${labels[e.status]||e.status} · ${time(e.time)}`;if(e.status==='failed')small.className='error';
      copy.append(heading,msg,small);row.append(initial,copy);feed.append(row);
    });
  }
  function renderHome(data){
    const summary=data.jobs||[], counts=data.counts||{};
    get('candidates').textContent=counts.running||0;get('read').textContent=counts.review||0;get('workers').textContent=connected?(counts.agents||0):'—';
    get('phase').textContent=counts.running?`${counts.running} pekerjaan sedang berjalan`:'Kantor sedang tenang';
    get('blocked').textContent=counts.review?`${counts.review} pekerjaan memerlukan tinjauan.`:'';
    get('sequence').textContent=summary[0]?`Aktivitas terakhir ${time(summary[0].time)}`:'Belum ada aktivitas tercatat';
    get('progress-title').textContent=counts.running?'Tim sedang mengerjakan tugasmu':'Semua anggota tetap ada di kantor';
    get('progress-status').textContent=!connected?'Koneksi terputus':counts.running?'Tim aktif':'Waktu santai';
    get('progress-status').dataset.status=!connected?'blocked':counts.running?'running':'idle';
    get('progress-caption').textContent=`${counts.running||0} berjalan · ${counts.review||0} perlu tinjauan · ${summary.filter(j=>done(j.status)).length} selesai dalam riwayat ini`;
    get('progress-note').textContent='Pilih pekerjaan untuk melihat tahapan dan hasilnya';
    const feed=get('events');feed.replaceChildren();
    summary.slice(0,6).forEach(job=>{
      const link=document.createElement('a');link.className='home-job';link.href='/riset?job_id='+encodeURIComponent(job.job_id);
      const name=document.createElement('strong');name.textContent=job.title;
      link.dataset.status=job.status;
      const state=document.createElement('span');state.className='job-status';state.textContent=labels[job.status]||job.status;
      const stamp=document.createElement('small');stamp.textContent=`Aktivitas terakhir ${time(job.time)}`;
      link.append(state,name,stamp);feed.append(link);
    });
    if(!summary.length){const empty=document.createElement('p');empty.className='caption';empty.textContent='Pekerjaan AAI akan muncul di sini saat dijalankan.';feed.append(empty);}
    const busy=summary.filter(job=>active(job.status)).flatMap(job=>job.agents||[]).filter(agent=>active(agent.status));
    roles.forEach((role,i)=>{
      const own=busy.filter(e=>roleOf(e)===i), working=connected&&own.length>0;
      character(i,working,working?title(own.at(-1)):role.idle);
    });
    const own=busy.filter(e=>roleOf(e)===selectedRole);
    get('detail').textContent=`${roles[selectedRole].name} · ${roles[selectedRole].role} — `+(own.length?title(own.at(-1)):`${roles[selectedRole].idle.toLowerCase()}, siap menerima tugas.`);
  }
  let homeData={jobs:[],counts:{}};
  async function loadHome(){
    try{
      const response=await fetch('/api/jobs',{cache:'no-store'});if(!response.ok)throw new Error('Home unavailable');
      homeData=await response.json();connected=true;get('connection').textContent=`Terhubung · diperbarui ${time(new Date().toISOString())}`;
    }catch(_){connected=false;get('connection').textContent='Koneksi putus · mencoba menyambung kembali';}
    renderHome(homeData);setTimeout(loadHome,2000);
  }
  async function load(){
    try{
      const response=await fetch('/api/progress',{cache:'no-store'});if(!response.ok)throw new Error('Monitor unavailable');
      const data=await response.json();events=Array.isArray(data.events)?data.events:[];connected=true;
      events.filter(e=>e.job_id).forEach(e=>jobs.set(e.job_id,e));
      if(followLatest&&jobs.size)selectedJob=[...events].reverse().find(e=>e.job_id)?.job_id||selectedJob;
      if(!followLatest&&selectedJob){
        const selectedResponse=await fetch('/api/progress?job_id='+encodeURIComponent(selectedJob),{cache:'no-store'});
        if(!selectedResponse.ok)throw new Error('Selected job unavailable');
        const selectedData=await selectedResponse.json();
        events=Array.isArray(selectedData.events)?selectedData.events:[];
        events.filter(e=>e.job_id).forEach(e=>jobs.set(e.job_id,e));
      }
      const picker=get('job-select'), previous=picker.value;picker.replaceChildren();
      if(!jobs.size){const opt=new Option('Menunggu pekerjaan','');picker.add(opt);}
      [...jobs.entries()].reverse().forEach(([id,e])=>picker.add(new Option(`${e.project_name||title(e)} · ${id.slice(0,8)}`,id)));
      picker.value=selectedJob||previous;
      get('connection').textContent=`Terhubung · diperbarui ${time(new Date().toISOString())}`;
      render();
    }catch(_){connected=false;get('connection').textContent='Koneksi putus · mencoba menyambung kembali';render();}
    // ponytail: reuse the existing two-second monitor cadence; streaming can replace it if needed.
    setTimeout(load,2000);
  }
  get('job-select').addEventListener('change',e=>{selectedJob=e.target.value;followLatest=false;render();});
  root.querySelector('[data-action=motion]').addEventListener('change',e=>root.querySelector('.shell').classList.toggle('motion-off',!e.target.checked));
  if(home){
    document.title='Beranda AAI';root.querySelector('h2').textContent='Beranda AAI';root.querySelector('.caption').textContent='Kantor virtual · semua pekerjaan dalam satu tempat';root.querySelector('.feed h3').textContent='Pekerjaan terakhir';root.querySelector('a[href="/workflow"].tool').href='/riset';root.querySelector('.tools a').textContent='Buka kantor riset';
    root.querySelectorAll('.metric').forEach((metric,i)=>metric.firstChild.textContent=['PEKERJAAN BERJALAN','PERLU TINJAUAN','AGENT AKTIF'][i]);
    renderHome(homeData);loadHome();
  }else{render();load();}
})();
