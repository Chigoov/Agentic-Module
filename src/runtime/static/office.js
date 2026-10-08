(() => {
  const root = document.getElementById('aai-studio-v2');
  const get = name => root.querySelector(`[data-value="${name}"]`);
  const roles = [
    {name:'Koordinator',short:'K',home:[43,35]},
    {name:'Pencarian',short:'P',home:[27,49]},
    {name:'Pembacaan',short:'B',home:[56,55]},
    {name:'Reviewer',short:'R',home:[48,72]}
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
  let selectedRole=0, selectedJob=new URLSearchParams(location.search).get('job_id')||'', followLatest=!selectedJob, events=[], connected=false;
  const time = value => {const d=new Date(value);return Number.isNaN(+d)?'—':d.toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit',second:'2-digit'});};
  roles.forEach((role,i)=>{
    const actor=document.createElement('div');actor.className='actor inactive';actor.setAttribute('aria-hidden','true');
    actor.innerHTML=`<div class="sprite" style="background-position-x:${i*100/3}%"></div><div class="nameplate waiting"><span class="dot"></span><span class="full">${role.name}</span><span class="short">${role.short}</span></div>`;
    actor.style.left=role.home[0]+'%';actor.style.top=role.home[1]+'%';actor.style.zIndex=role.home[1];get('actors').append(actor);actors.push(actor);
    const card=document.createElement('button');card.type='button';card.className='agent';
    card.innerHTML=`<span class="portrait" aria-hidden="true" style="background-position-x:${i*100/3}%"></span><span class="agent-copy"><strong>${role.name}</strong><span class="task"></span><span class="state"></span></span>`;
    card.addEventListener('click',()=>{selectedRole=i;render(false);});get('cards').append(card);cards.push(card);
  });
  function render(animate=true){
    const scoped=events.filter(e=>e.job_id===selectedJob), latest=scoped.at(-1);
    const lifecycle=new Map(), roleEvents=roles.map(()=>[]);
    scoped.forEach(e=>{if(e.event_kind==='agent'||e.event_kind==='job')lifecycle.set(e.agent_id,e);roleEvents[roleOf(e)].push(e);});
    const jobEnd=[...scoped].reverse().find(e=>e.event_kind==='job');
    const terminal=jobEnd&&!active(jobEnd.status);
    const currentAgents=[...lifecycle.values()].filter(e=>active(e.status)&&!terminal);
    get('workers').textContent=String(currentAgents.length);
    get('phase').textContent=latest?`${title(latest)} · ${labels[latest.status]||latest.status}`:'Menunggu pekerjaan';
    get('sequence').textContent=latest?`Aktivitas terakhir ${time(latest.time)}`:'Menunggu aktivitas';
    const candidates=[...scoped].reverse().find(e=>Number.isFinite(e.unique)||Number.isFinite(e.count));
    const retrieved=[...scoped].reverse().find(e=>Number.isFinite(e.retrieved));
    get('candidates').textContent=candidates?(candidates.unique??candidates.count):'—';
    get('read').textContent=retrieved?retrieved.retrieved:'—';
    get('blocked').textContent=jobEnd&&['partial','blocked','pending'].includes(jobEnd.status)?'Hasil masih memerlukan tinjauan.':jobEnd?.status==='failed'?'Pekerjaan gagal. Periksa catatan aktivitas.':'';
    roles.forEach((role,i)=>{
      const own=roleEvents[i], last=own.at(-1), working=connected&&!terminal&&(currentAgents.some(e=>roleOf(e)===i)||active(last?.status));
      const state=working?'running':last?(terminal&&!done(jobEnd.status)?jobEnd.status:last.status):'idle';
      const actor=actors[i], previous=actor.dataset.state;
      const xy=done(state)&&i>0?[39+i*4,40+i*3]:role.home;
      actor.classList.toggle('selected',selectedRole===i);actor.classList.toggle('inactive',!last);
      actor.querySelector('.nameplate').classList.toggle('waiting',!working);
      actor.classList.toggle('working',working);actor.style.left=xy[0]+'%';actor.style.top=xy[1]+'%';actor.style.zIndex=xy[1];
      if(animate&&previous&&previous!==state&&done(state)&&i>0){actor.classList.add('walking');setTimeout(()=>actor.classList.remove('walking'),1950);}
      actor.dataset.state=state;cards[i].setAttribute('aria-pressed',String(selectedRole===i));
      cards[i].querySelector('.task').textContent=last?title(last):'Belum ada aktivitas tercatat';
      cards[i].querySelector('.state').textContent=(!connected&&last?'Koneksi putus · ':'')+(labels[state]||state);
    });
    const detail=roleEvents[selectedRole].at(-1);
    get('detail').textContent=detail?(detail.message&&detail.message!==detail.stage?detail.message:title(detail)):`${roles[selectedRole].name} — belum ada aktivitas tercatat untuk pekerjaan ini.`;
    const feed=get('events');feed.replaceChildren();
    scoped.slice(-8).reverse().forEach(e=>{
      const row=document.createElement('div');row.className='event';const initial=document.createElement('span');initial.className='initial';initial.textContent=roles[roleOf(e)].short;
      const copy=document.createElement('div');copy.className='event-copy';const heading=document.createElement('strong');heading.textContent=title(e);
      const msg=document.createElement('span');msg.textContent=e.message===e.stage?'':(e.message||'');
      const small=document.createElement('small');small.textContent=`${labels[e.status]||e.status} · ${time(e.time)}`;if(e.status==='failed')small.className='error';
      copy.append(heading,msg,small);row.append(initial,copy);feed.append(row);
    });
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
    }catch(_){connected=false;get('connection').textContent='Koneksi putus · mencoba menyambung kembali';render(false);}
    // ponytail: reuse the existing two-second monitor cadence; streaming can replace it if needed.
    setTimeout(load,2000);
  }
  get('job-select').addEventListener('change',e=>{selectedJob=e.target.value;followLatest=false;render(false);});
  root.querySelector('[data-action=motion]').addEventListener('change',e=>root.querySelector('.shell').classList.toggle('motion-off',!e.target.checked));
  render(false);load();
})();
