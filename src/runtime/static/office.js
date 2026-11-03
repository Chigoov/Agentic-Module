(() => {
  const root = document.getElementById('aai-studio-v2');
  const home = root.dataset.view === 'home';
  const bengkel = root.dataset.view === 'bengkel';
  const profile = bengkel?'bengkel':'asistenriset';
  const get = name => root.querySelector(`[data-value="${name}"]`);
  const roles = [
    {name:'Arka',role:'Koordinator',short:'A',home:[39,37],rest:[66,50],idle:'Menikmati kopi'},
    {name:'Dinda',role:'Pencarian',short:'D',home:[22,51],rest:[29,53],idle:'Membaca buku'},
    {name:'Fajar',role:'Pembacaan',short:'F',home:[52,56],rest:[40,59],idle:'Peregangan ringan'},
    {name:'Salsa',role:'Reviewer',short:'S',home:[44,73],rest:[48,84],idle:'Bersantai sejenak'}
  ];
  const labels = {running:'Sedang bekerja',started:'Sedang bekerja',completed:'Selesai',success:'Selesai',partial:'Perlu ditinjau',pending:'Menunggu',blocked:'Terhambat',failed:'Gagal',cancelled:'Dibatalkan',unknown:'Status belum diketahui',idle:'Belum dijalankan'};
  const stages = {task_analysis:'Memahami tugas',planning:'Menyusun rencana',discovery:'Mencari sumber',deduplication:'Menghapus duplikat',ranking:'Memeringkat kandidat',verification:'Memeriksa metadata',access_check:'Memeriksa akses',retrieval:'Membaca dokumen',evidence_extraction:'Mengambil bukti',claim_verification:'Memeriksa klaim',human_review:'Menunggu tinjauan',synthesis:'Menyusun sintesis',writing:'Menulis',citation_audit:'Memeriksa sitasi',fact_audit:'Memeriksa fakta',docx_generation:'Membuat dokumen',task_analyzer_agent:'Analisis tugas',research_planner_agent:'Perencanaan',retrieval_agent:'Pembacaan dokumen',evidence_agent:'Ekstraksi bukti',academic_writing_workflow:'Alur penulisan',deep_research_workflow:'Alur riset',orchestrator_agent:'Koordinasi'};
  if(bengkel)roles.forEach((role,i)=>role.role=['Koordinator bengkel','Diagnosis & inspeksi','Perbaikan kode','Tes & build'][i]);
  if(home)roles.forEach((role,i)=>role.role=['Koordinator','Sumber & diagnosis','Dokumen & kode','Verifikasi & tes'][i]);
  const activities={search:'Menelusuri sumber',read:bengkel?'Memeriksa kode':'Membaca dokumen',code:'Memperbaiki kode',test:'Menjalankan tes',build:'Membangun aplikasi',review:'Memeriksa hasil',report:'Menyusun laporan',execute:'Menjalankan perintah',model:'Menyiapkan langkah',answer:'Menulis jawaban',waiting:'Menunggu jawabanmu'};
  const activityOf=e=>e?.activity||({hermes_model:'model',hermes_answer:'answer'})[e?.stage]||(/retriev|evidence/.test(e?.stage||'')?'read':/search|discovery/.test(e?.stage||'')?'search':/audit|verif/.test(e?.stage||'')?'review':'model');
  const active = s => ['running','started'].includes(s);
  const done = s => ['completed','success'].includes(s);
  const roleOf = e => {
    if(Number.isInteger(e.visual_role)&&e.visual_role>=0&&e.visual_role<roles.length)return e.visual_role;
    if(e.event_kind === 'job' && /workflow|orchestrator|integration_check|instruction/.test(e.stage || '')) return 0;
    const name = `${e.stage || ''} ${e.agent_id || ''}`;
    if(/audit|verification|review|conflict|claim/.test(name)) return 3;
    if(/retriev|evidence|reading|pdf/.test(name)) return 2;
    if(/discovery|search|deduplication|ranking/.test(name)) return 1;
    return 0;
  };
  Object.assign(stages, {instruction:'Tugas diterima',integration_check:'Pemeriksaan integrasi',citation_audit_agent:'Audit sitasi',fact_audit_agent:'Audit fakta',human_style_audit_agent:'Audit bahasa'});
  const title = e => e.source==='hermes'?(activities[e.activity]||e.tool_name||({hermes_model:'Menyiapkan langkah',hermes_answer:'Menulis jawaban',hermes_turn:'Chat Hermes',hermes_connection:'Sambungan Hermes'})[e.stage]||'Aktivitas Hermes'):stages[e.stage] || String(e.stage || 'Aktivitas').replaceAll('_',' ');
  const checkOutcome=e=>active(e.status)?'running':e.outcome==='failed'||e.status==='failed'?'failed':e.outcome==='passed'?'passed':'unconfirmed';
  const actors=[], cards=[], jobs=new Map();
  const shell=root.querySelector('.shell'), reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  // ponytail: short floor routes reuse the existing sprites; idle movement never creates job events.
  const strolls=[[[65,53],[64,55]],[[30,55],[31,55]],[[39,62],[38,64]],[[46,82],[44,79]]];
  const idleSteps=roles.map(()=>0);
  const motionAllowed=()=>connected&&!document.hidden&&!reducedMotion.matches&&!shell.classList.contains('motion-off');
  root.querySelector(`[data-nav="${root.dataset.view}"]`).setAttribute('aria-current','page');
  const params=new URLSearchParams(location.search),session=params.get('session_id')||'';
  let selectedRole=0, selectedJob=params.get('job_id')||(session?`hermes:${profile}:${session}`:''), events=[], connected=false;
  const time = value => {const d=new Date(value);return Number.isNaN(+d)?'—':d.toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit',second:'2-digit'});};
  let workflowPanel, workflowTrack, workflowSummary, workflowDetail, selectedStep='';
  if(!home){
    workflowPanel=document.createElement('section');workflowPanel.className='live-workflow';workflowPanel.setAttribute('aria-label','Workflow live sesi terpilih');
    const heading=document.createElement('h3');heading.textContent='Workflow live';
    workflowSummary=document.createElement('p');workflowSummary.className='caption';
    const note=document.createElement('p');note.className='caption';note.textContent='Urutan operasi yang tercatat pada giliran tugas ini. Langkah sejenis berurutan diringkas dalam satu kartu; klik kartu untuk melihat rinciannya. Ini jejak pelaksanaan, bukan rencana langkah yang belum dijalankan.';
    const latestButton=document.createElement('button');latestButton.type='button';latestButton.className='tool';latestButton.textContent='Langkah terbaru';
    workflowTrack=document.createElement('ol');workflowTrack.className='workflow-track';workflowTrack.setAttribute('aria-label','Urutan pelaksanaan');
    workflowDetail=document.createElement('details');workflowDetail.className='workflow-detail';
    latestButton.addEventListener('click',()=>{const last=workflowTrack.querySelector('li:last-child button');if(last){last.click();last.focus({preventScroll:true});workflowTrack.scrollLeft=workflowTrack.scrollWidth;}});
    workflowPanel.append(heading,workflowSummary,note,latestButton,workflowTrack,workflowDetail);root.querySelector('.progress-panel').after(workflowPanel);
  }
  let checksPanel, checksSummary, checksFilter, checksList;
  if(bengkel){
    checksPanel=document.createElement('details');checksPanel.className='check-panel';checksPanel.id='check-history';
    checksSummary=document.createElement('summary');checksSummary.textContent='Rincian tes & build';
    const note=document.createElement('p');note.className='caption';note.textContent='Angka menghitung perintah yang selesai pada giliran tugas ini. Percobaan ulang dihitung terpisah; perintah yang masih berjalan belum masuk penyebut. Nama kasus tes dan alasan kegagalan hanya tersedia jika dilaporkan Hermes di chat.';
    const filterLabel=document.createElement('label');filterLabel.className='check-filter';filterLabel.textContent='Tampilkan ';
    checksFilter=document.createElement('select');checksFilter.setAttribute('aria-label','Filter hasil tes dan build');
    [['all','Semua hasil'],['passed','Berhasil'],['failed','Gagal'],['unconfirmed','Belum terkonfirmasi'],['running','Sedang berjalan']].forEach(([value,label])=>checksFilter.add(new Option(label,value)));
    checksFilter.addEventListener('change',()=>render());filterLabel.append(checksFilter);
    checksList=document.createElement('div');checksList.className='check-list';checksPanel.append(checksSummary,note,filterLabel,checksList);
    root.querySelector('.progress-panel').after(checksPanel);
    const read=get('read'),button=document.createElement('button');button.type='button';button.className='check-open';button.setAttribute('aria-controls',checksPanel.id);button.setAttribute('aria-expanded','false');
    const hint=document.createElement('span');hint.textContent='Lihat rincian';read.replaceWith(button);button.append(read,hint);
    button.addEventListener('click',()=>{checksPanel.open=!checksPanel.open;if(checksPanel.open){checksPanel.scrollIntoView({block:'nearest',behavior:'instant'});checksSummary.focus();}});
    checksPanel.addEventListener('toggle',()=>button.setAttribute('aria-expanded',String(checksPanel.open)));
  }
  // ponytail: clip the existing room image for furniture depth; no duplicate raster assets or 3D engine.
  [
    [40,[[444,203],[498,232],[498,283],[444,251]]],
    [54,[[240,316],[298,350],[298,389],[240,357]]],
    [59,[[597,355],[652,387],[652,432],[597,399]]],
    [76,[[498,491],[553,524],[553,572],[498,536]]]
  ].forEach(([depth,points])=>{
    const desk=root.querySelector('.room').cloneNode();desk.className='room furniture';desk.alt='';desk.setAttribute('aria-hidden','true');
    desk.style.clipPath='polygon('+points.map(([x,y])=>`${x/12}% ${y/8}%`).join(',')+')';desk.style.zIndex=depth;
    root.querySelector('.world').append(desk);
  });
  roles.forEach((role,i)=>{
    const actor=document.createElement('button');actor.type='button';actor.className='actor idle';
    actor.style.setProperty('--work-x',(i%2)*100+'%');actor.style.setProperty('--work-y',Math.floor(i/2)*100+'%');
    actor.style.setProperty('--work-center',[-6.7,.8,-8.9,-1.3][i]+'%');actor.style.setProperty('--work-ground',[1.6,1.4,4.1,4.1][i]+'%');
    actor.style.setProperty('--idle-center',[-14.1,-9.1,.9,2.1][i]+'%');actor.style.setProperty('--idle-ground',[3.3,4.1,3.7,3.7][i]+'%');
    actor.innerHTML=`<span class="sprite" aria-hidden="true" style="background-position-x:${i*100/3}%"></span><span class="work-prop" aria-hidden="true"></span><span class="nameplate waiting"><span class="dot"></span><span><strong>${role.name}</strong><span class="activity">${role.idle}</span></span></span>`;
    actor.style.left=role.rest[0]+'%';actor.style.top=role.rest[1]+'%';actor.style.zIndex=role.rest[1];get('actors').append(actor);actors.push(actor);
    const card=document.createElement('button');card.type='button';card.className='agent';
    card.innerHTML=`<span class="portrait" aria-hidden="true" style="background-position-x:${i*100/3}%"></span><span class="agent-copy"><strong>${role.name}</strong><span class="role">${role.role}</span><span class="task"></span><span class="state"></span></span>`;
    const select=()=>{
      selectedRole=i;if(home)renderHome(homeData);else render();
      if(motionAllowed()&&!actor.classList.contains('working')) actor.querySelector('.sprite').animate([{transform:'translateY(0)'},{transform:'translateY(-5px) rotate(-3deg)'},{transform:'translateY(0)'}],{duration:550});
    };
    actor.addEventListener('click',select);card.addEventListener('click',select);get('cards').append(card);cards.push(card);
  });
  function character(i,working,task,activity='model'){
    const role=roles[i],actor=actors[i];
    if(!connected)working=actor.classList.contains('working');
    const changed=actor.classList.contains('working')!==working;
    if(working)idleSteps[i]=0;
    const xy=working?role.home:[role.rest,...strolls[i]][idleSteps[i]];
    actor.classList.toggle('working',working);actor.classList.toggle('idle',!working);
    actor.dataset.activity=working?activity:'idle';
    actor.querySelector('.work-prop').textContent=({search:'⌕',read:'▤',code:'</>',test:'✓',build:'⚙',review:'⌕ ✓',report:'✎',execute:'>_',model:'···',answer:'✎'})[activity]||'···';
    actor.classList.toggle('selected',selectedRole===i);actor.classList.toggle('offline',!connected);
    actor.querySelector('.nameplate').classList.toggle('waiting',!working);
    actor.querySelector('.activity').textContent=!connected?'Koneksi terputus':working?task:role.idle;
    if(connected){
      const moved=actor.style.left!==xy[0]+'%'||actor.style.top!==xy[1]+'%';
      // ponytail: seated poses stay at their calibrated desk; animate only standing floor routes.
      actor.classList.toggle('walking',moved&&!working&&!changed&&motionAllowed());
      if(changed)actor.style.transition='none';
      actor.style.left=xy[0]+'%';actor.style.top=xy[1]+'%';actor.style.zIndex=Math.round(xy[1]);
      if(changed){void actor.offsetWidth;actor.style.transition='';}
    }else actor.classList.remove('walking');
    actor.setAttribute('aria-label',`${role.name}, ${role.role}: ${!connected?'koneksi terputus':working?task:role.idle}`);
    actor.setAttribute('aria-pressed',String(selectedRole===i));actor.dataset.state=!connected?'offline':working?'running':'idle';
    cards[i].setAttribute('aria-pressed',String(selectedRole===i));cards[i].dataset.state=actor.dataset.state;
    cards[i].querySelector('.task').textContent=working?task:role.idle;
    cards[i].querySelector('.state').textContent=!connected?'Koneksi terputus':working?'Sedang bekerja':'Siap menerima tugas';
  }
  actors.forEach(actor=>actor.addEventListener('transitionend',e=>{if(e.propertyName==='left'||e.propertyName==='top')actor.classList.remove('walking');}));
  let idleTurn=0;
  setInterval(()=>{
    if(!motionAllowed())return;
    const i=idleTurn++%roles.length;
    if(actors[i].dataset.state!=='idle')return;
    idleSteps[i]=(idleSteps[i]+1)%3;
    character(i,false,roles[i].idle);
  },3000);
  function progress(scoped,jobEnd){
    // ponytail: show recorded stages, not a guessed percentage of an unknown workflow.
    const steps=new Map(),stageEvents=scoped.filter(e=>!e.event_kind);
    (stageEvents.length?stageEvents:scoped.filter(e=>e.event_kind==='agent')).forEach(e=>steps.set(e.tool_name?e.agent_id:e.stage,e));
    const recorded=[...steps.values()],finished=recorded.filter(e=>done(e.status)).length;
    const status=jobEnd?.status||scoped.at(-1)?.status||'idle';
    get('progress-status').textContent=labels[status]||status;get('progress-status').dataset.status=status;
    get('progress-title').textContent=scoped[0]?.project_name||'Belum ada pekerjaan dipilih';
    get('progress-caption').textContent=recorded.length?`${finished} dari ${recorded.length} aktivitas tercatat selesai · giliran tugas saat ini`:'Aktivitas akan muncul saat pekerjaan berjalan';
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
  function workflow(scoped,jobEnd){
    // ponytail: reuse the safe tool events, retain first-start order, and collapse only consecutive activities.
    const operations=new Map();scoped.filter(e=>e.tool_name).forEach(e=>operations.set(e.agent_id||`seq:${e.seq}`,e));
    const groups=[];
    [...operations.values()].forEach(e=>{const kind=activityOf(e),last=groups.at(-1);if(last?.kind===kind)last.items.push(e);else groups.push({kind,key:e.agent_id||`seq:${e.seq}`,items:[e]});});
    const state=e=>active(e.status)&&jobEnd&&!active(jobEnd.status)?'pending':['test','build'].includes(activityOf(e))?checkOutcome(e):active(e.status)?'running':e.status==='failed'?'failed':done(e.status)?'completed':'pending';
    const stateLabels={passed:'Berhasil',completed:'Selesai',failed:'Gagal',unconfirmed:'Belum terkonfirmasi',running:'Sedang berjalan',pending:'Belum tercatat selesai'};
    workflowSummary.textContent=`${operations.size} operasi · ${groups.length} langkah berurutan · ${!connected?'koneksi terputus, catatan terakhir':labels[jobEnd?.status||scoped.at(-1)?.status]||'Menunggu tugas'}`;
    const scroll=workflowTrack.scrollLeft;workflowTrack.replaceChildren();
    if(!groups.some(group=>group.key===selectedStep))selectedStep=groups.at(-1)?.key||'';
    const showDetail=group=>{
      selectedStep=group.key;workflowDetail.replaceChildren();
      const summary=document.createElement('summary');summary.textContent=`Rincian ${activities[group.kind]||group.kind} · ${group.items.length} operasi`;workflowDetail.append(summary);
      const list=document.createElement('ol');list.className='workflow-operations';
      group.items.forEach(e=>{const row=document.createElement('li');row.dataset.state=state(e);const name=document.createElement('strong');name.textContent=`${e.tool_name} · ${stateLabels[state(e)]}`;const stamp=document.createElement('small');stamp.textContent=`${time(e.time)} · ${roles[roleOf(e)].name} · Operasi ${e.agent_id||e.seq}`;row.append(name,stamp);list.append(row);});workflowDetail.append(list);
      workflowTrack.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.step===selectedStep)));
    };
    groups.forEach((group,i)=>{
      const states=group.items.map(state),current=states.includes('running')?'running':states.includes('failed')?'failed':states.includes('unconfirmed')?'unconfirmed':states.includes('pending')?'pending':'completed';
      const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.className='workflow-step';button.dataset.step=group.key;button.dataset.status=current;button.setAttribute('aria-pressed',String(selectedStep===group.key));
      const name=document.createElement('strong');name.textContent=`${i+1}. ${activities[group.kind]||group.kind}`;
      const status=document.createElement('span');status.textContent=`${group.items.length} operasi · ${stateLabels[current]}`;
      const stamp=document.createElement('small');stamp.textContent=`${time(group.items[0].time)} – ${time(group.items.at(-1).time)}`;
      if(i&&groups[i-1].items.some(e=>state(e)==='failed')){const after=document.createElement('small');after.className='workflow-return';after.textContent='Langkah setelah kegagalan';button.append(after);}
      button.append(name,status,stamp);button.addEventListener('click',()=>{showDetail(group);workflowDetail.open=true;});li.append(button);workflowTrack.append(li);
    });
    if(groups.length)showDetail(groups.find(group=>group.key===selectedStep));
    else{workflowDetail.replaceChildren();const empty=document.createElement('li');empty.className='caption';empty.textContent='Menunggu operasi pertama dari tugas yang dipilih.';workflowTrack.append(empty);}
    workflowTrack.scrollLeft=scroll;
  }
  function render(){
    const ownEvents=events.filter(e=>e.job_id===selectedJob);
    const turn=ownEvents.findLastIndex(e=>e.source==='hermes'&&e.stage==='hermes_turn'&&active(e.status)&&e.seq>=0);
    const scoped=ownEvents.slice(Math.max(0,turn)), latest=scoped.at(-1);
    const lifecycle=new Map(), roleEvents=roles.map(()=>[]);
    scoped.forEach(e=>{
      if(e.source==='hermes'&&e.event_kind==='job'&&e.stage==='hermes_turn'&&active(e.status)){
        lifecycle.clear();roleEvents.forEach(own=>own.length=0);
      }
      if(e.event_kind==='agent'||(e.event_kind==='job'&&e.source!=='hermes'))lifecycle.set(e.agent_id,e);
      roleEvents[roleOf(e)].push(e);
    });
    const jobEnd=[...scoped].reverse().find(e=>e.event_kind==='job');
    const terminal=jobEnd&&!active(jobEnd.status);
    const currentAgents=[...lifecycle.values()].filter(e=>active(e.status)&&!terminal);
    progress(scoped,jobEnd);
    workflow(scoped,jobEnd);
    if(bengkel){
      const board=get('bench-flow');board.replaceChildren();
      [['Inspeksi & diagnosis',['read','search','review']],['Perbaikan kode',['code']],['Pengujian',['test']],['Build',['build']],['Laporan',['report','answer']]].forEach(([label,kinds])=>{
        const last=scoped.filter(e=>kinds.includes(activityOf(e))).at(-1),state=last?.status||'idle';
        const phase=document.createElement('div');phase.className='bench-phase';phase.dataset.status=terminal&&active(state)?'pending':state;
        const name=document.createElement('strong');name.textContent=label;
        const status=document.createElement('small');status.textContent=!last?'Belum tercatat':terminal&&active(state)?'Belum tercatat selesai':labels[state]||state;
        phase.append(name,status);board.append(phase);
      });
    }
    get('workers').textContent=connected?String(currentAgents.length):'—';
    get('phase').textContent=latest?`${title(latest)} · ${labels[latest.status]||latest.status}`:'Menunggu pekerjaan';
    get('sequence').textContent=latest?`Aktivitas terakhir ${time(latest.time)}`:'Menunggu aktivitas';
    const candidates=[...scoped].reverse().find(e=>Number.isFinite(e.unique)||Number.isFinite(e.count));
    const retrieved=[...scoped].reverse().find(e=>Number.isFinite(e.retrieved));
    get('candidates').textContent=candidates?(candidates.unique??candidates.count):'—';
    get('read').textContent=retrieved?retrieved.retrieved:'—';
    if(bengkel){
      get('candidates').textContent=scoped.filter(e=>e.tool_name&&done(e.status)).length;
      // ponytail: one latest row per tool operation supplies both the count and its inspectable list.
      const operations=new Map();scoped.filter(e=>e.tool_name&&['test','build'].includes(e.activity)).forEach(e=>operations.set(e.agent_id||`seq:${e.seq}`,e));
      const checks=[...operations.values()].filter(e=>!active(e.status));
      const counts={passed:0,failed:0,unconfirmed:0,running:0};
      const outcome=checkOutcome;
      [...operations.values()].forEach(e=>counts[outcome(e)]++);
      get('read').textContent=checks.length?`${counts.passed}/${checks.length}`:'—';
      checksSummary.textContent=`Rincian tes & build · ${counts.passed} berhasil · ${counts.failed} gagal · ${counts.unconfirmed} belum terkonfirmasi · ${counts.running} berjalan`;
      const scroll=checksList.scrollTop;checksList.replaceChildren();
      [...operations.values()].reverse().filter(e=>checksFilter.value==='all'||outcome(e)===checksFilter.value).forEach(e=>{
        const state=outcome(e),row=document.createElement('div');row.className='check-row';row.dataset.outcome=state;
        const name=document.createElement('strong');name.textContent=`${e.activity==='build'?'Build':'Tes'} · ${e.tool_name}`;
        const result=document.createElement('span');result.className='check-result';result.textContent=({passed:'Berhasil',failed:'Gagal',unconfirmed:'Belum terkonfirmasi',running:'Sedang berjalan'})[state];
        const stamp=document.createElement('small');stamp.textContent=`${time(e.time)} · ${roles[roleOf(e)].name} · Operasi ${e.agent_id||e.seq}`;
        const reason=document.createElement('p');reason.textContent=({passed:'Perintah melaporkan exit code 0.',failed:'Perintah melaporkan kegagalan. Rincian penyebab dapat diperiksa di chat Hermes.',unconfirmed:'Belum ada hasil terkonfirmasi; selesai dijalankan tidak selalu berarti berhasil.',running:'Menunggu hasil perintah; belum dihitung pada angka berhasil/selesai.'})[state];
        row.append(name,result,stamp,reason);checksList.append(row);
      });
      if(!checksList.childElementCount){const empty=document.createElement('p');empty.className='caption';empty.textContent=operations.size?'Tidak ada pemeriksaan dengan filter ini.':'Belum ada perintah tes atau build tercatat pada giliran tugas ini.';checksList.append(empty);}
      checksList.scrollTop=scroll;
    }
    get('blocked').textContent=jobEnd&&['partial','blocked','pending'].includes(jobEnd.status)?'Hasil masih memerlukan tinjauan.':jobEnd?.status==='failed'?'Pekerjaan gagal. Periksa catatan aktivitas.':'';
    roles.forEach((role,i)=>{
      const last=currentAgents.filter(e=>roleOf(e)===i).at(-1), working=connected&&!terminal&&!!last;
      character(i,working,last?title(last):role.idle,activityOf(last));
    });
    const detail=roleEvents[selectedRole].at(-1);
    get('detail').textContent=`${roles[selectedRole].name} · ${roles[selectedRole].role} — `+(detail?`${title(detail)} · ${labels[detail.status]||detail.status}`:`${roles[selectedRole].idle}, siap menerima tugas.`);
    const feed=get('events');feed.replaceChildren();
    scoped.slice(-8).reverse().forEach(e=>{
      const row=document.createElement('div');row.className='event';const initial=document.createElement('span');initial.className='initial';initial.textContent=roles[roleOf(e)].short;
      const copy=document.createElement('div');copy.className='event-copy';const heading=document.createElement('strong');heading.textContent=title(e);
      const msg=document.createElement('span');msg.textContent=e.tool_name?`${e.tool_name}${['test','build'].includes(e.activity)?' · '+(active(e.status)?'berjalan':({passed:'perintah berhasil',failed:'perintah gagal',unconfirmed:'hasil belum terkonfirmasi'})[e.outcome||'unconfirmed']):''}`:e.message===e.stage?'':(e.message||'');
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
      const link=document.createElement('a');link.className='home-job';link.href=(job.profile==='bengkel'?'/bengkel':'/riset')+'?job_id='+encodeURIComponent(job.job_id);
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
      character(i,working,working?`${own.at(-1).profile||'AAI'} · ${title(own.at(-1))}`:role.idle,activityOf(own.at(-1)));
    });
    const own=busy.filter(e=>roleOf(e)===selectedRole);
    get('detail').textContent=`${roles[selectedRole].name} · ${roles[selectedRole].role} — `+(own.length?title(own.at(-1)):`${roles[selectedRole].idle.toLowerCase()}, siap menerima tugas.`);
  }
  let homeData={jobs:[],counts:{}};
  const connectionLabel=data=>`Terhubung · ${data.hermes?.connected?'Hermes langsung':data.hermes?.status||'AAI'} · ${time(new Date().toISOString())}`;
  async function loadHome(schedule=true){
    try{
      const response=await fetch('/api/jobs',{cache:'no-store'});if(!response.ok)throw new Error('Home unavailable');
      homeData=await response.json();connected=true;get('connection').textContent=connectionLabel(homeData);
      root.dataset.hermesRevision=homeData.hermes?.revision||0;
    }catch(_){connected=false;get('connection').textContent='Koneksi putus · mencoba menyambung kembali';}
    renderHome(homeData);if(schedule)setTimeout(loadHome,2000);
  }
  async function load(schedule=true){
    try{
      const overview=await fetch('/api/jobs?profile='+profile,{cache:'no-store'});if(!overview.ok)throw new Error('Jobs unavailable');
      const data=await overview.json();jobs.clear();(data.jobs||[]).forEach(j=>jobs.set(j.job_id,{project_name:j.title,...j}));
      if(!selectedJob&&jobs.size)selectedJob=([...jobs.values()].find(j=>active(j.status))||[...jobs.values()][0]).job_id;
      const response=await fetch('/api/progress?'+new URLSearchParams(selectedJob?{job_id:selectedJob}:{profile}),{cache:'no-store'});
      if(!response.ok)throw new Error('Monitor unavailable');
      const progressData=await response.json();events=Array.isArray(progressData.events)?progressData.events:[];connected=true;
      root.dataset.hermesRevision=progressData.hermes?.revision||0;
      root.dataset.jobId=selectedJob;
      if(selectedJob&&!jobs.has(selectedJob))jobs.set(selectedJob,{project_name:events[0]?.project_name||'Sesi yang dipilih'});
      const picker=get('job-select'), previous=picker.value;picker.replaceChildren();
      if(!jobs.size){const opt=new Option('Menunggu pekerjaan','');picker.add(opt);}
      [...jobs.entries()].forEach(([id,e])=>picker.add(new Option(e.project_name||id,id)));
      picker.value=selectedJob||previous;
      get('connection').textContent=connectionLabel(data);
      render();
    }catch(_){connected=false;get('connection').textContent='Koneksi putus · mencoba menyambung kembali';render();}
    // ponytail: retain polling as a backstop; native EventSource triggers immediate refreshes.
    if(schedule)setTimeout(load,2000);
  }
  get('job-select').addEventListener('change',e=>{selectedJob=e.target.value;history.replaceState(null,'','?'+new URLSearchParams({job_id:selectedJob}));load(false);});
  root.querySelector('[data-action=motion]').addEventListener('change',e=>{
    shell.classList.toggle('motion-off',!e.target.checked);
    if(!e.target.checked)actors.forEach((actor,i)=>{
      actor.classList.remove('walking');
      actor.querySelector('.sprite').getAnimations().filter(animation=>!(animation instanceof CSSAnimation)).forEach(animation=>animation.cancel());
      if(actor.dataset.state==='idle'){idleSteps[i]=0;character(i,false,roles[i].idle);}
    });
  });
  root.querySelector('[data-action=focus]').addEventListener('click',e=>{
    const focused=shell.classList.toggle('focus-office');
    e.currentTarget.setAttribute('aria-pressed',String(focused));e.currentTarget.textContent=focused?'Tampilkan panel':'Fokus kantor';
  });
  if(home){
    document.title='Beranda AAI';root.querySelector('h2').textContent='Beranda AAI';root.querySelector('.caption').textContent='Kantor virtual · semua pekerjaan dalam satu tempat';root.querySelector('.feed h3').textContent='Pekerjaan terakhir';root.querySelector('a[href="/workflow"].tool').href='/riset';root.querySelector('.tools a').textContent='Buka kantor riset';
    root.querySelectorAll('.metric').forEach((metric,i)=>metric.firstChild.textContent=['PEKERJAAN BERJALAN','PERLU TINJAUAN','AGENT AKTIF'][i]);
    renderHome(homeData);loadHome();
  }else{
    if(bengkel){
      document.title='Bengkel Hermes';root.querySelector('h2').textContent='Bengkel Hermes';root.querySelector('.brandmark').textContent='DEV';root.querySelector('.caption').textContent='GAME-TRADING-SAHAM-3D · inspeksi, diagnosis, kode, tes & build';root.querySelector('.feed h3').textContent='Aktivitas bengkel';
      root.querySelectorAll('.metric').forEach((metric,i)=>metric.firstChild.textContent=['OPERASI SELESAI','PERINTAH TES/BUILD BERHASIL','PELAKSANA AKTIF'][i]);
      root.querySelector('.scene-note').textContent='Bengkel perangkat lunak · karakter mengikuti alat yang sedang bekerja';
    }
    render();load();
  }
  const stream=new EventSource('/api/events');let refreshTimer;
  stream.onmessage=()=>{clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>home?loadHome(false):load(false),30);};
  addEventListener('pagehide',()=>stream.close());
  document.addEventListener('visibilitychange',()=>shell.classList.toggle('motion-paused',document.hidden));
  addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
})();
