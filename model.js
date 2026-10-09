(function (root) {
  'use strict';
  // ponytail: browser-local demo state; move ownership, jobs, and entitlements to a server before real transactions.
  const DAY = 86400000;
  const templates = [
    { id: 'studio', name: 'Studio Keluarga', occasion: 'Studio', people: 4, attire: 'Linen netral', description: 'Foto bareng yang simpel dan hangat. Cocok dipajang di rumah.', image: 'assets/studio.png', faces: [[.416,.184],[.607,.258],[.397,.471],[.633,.555]] },
    { id: 'home', name: 'Momen di Rumah', occasion: 'Di rumah', people: 3, attire: 'Kasual senada', description: 'Santai di rumah, dekat sama orang tersayang.', image: 'assets/home.png', faces: [[.339,.269],[.510,.466],[.671,.326]] },
    { id: 'lebaran', name: 'Lebaran Bersama', occasion: 'Lebaran', people: 2, attire: 'Pakaian Lebaran sage', description: 'Lebaran makin lengkap dengan foto bareng orang tersayang.', image: 'assets/lebaran.png', faces: [[.391,.241],[.646,.308]] }
  ];
  const uid = prefix => prefix + '-' + (root.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2)).slice(0, 10);
  const copy = value => JSON.parse(JSON.stringify(value));
  const template = id => templates.find(t => t.id === id);
  const project = (s,id) => s.projects.find(p => p.id === id && !p.deleted);
  const current = p => p.versions.find(v => v.id === p.currentVersion);
  const activeJob = p => p.job && ['queued','processing','delayed'].includes(p.job.status);
  function initial() {
    return { schema: 1, verified: false, creationsUsed: 0, projects: [], orders: [], tickets: [], events: [], controls: { admission: true, outage: false, concurrency: 2, retries: 2, budget: 50000, unitCost: 1500 }, catalog: Object.fromEntries(templates.map(t => [t.id, { published: true, regions: true, evidence: true, version: 1 }])) };
  }
  function log(s,type,details={}) {
    s.events.unshift({ id:uid('evt'), type, at:Date.now(), ...details });
    s.events = s.events.slice(0,300);
  }
  function createProject(s,tid) {
    if (!s.catalog[tid]?.published || !template(tid)) throw Error('Template ini sedang tidak tersedia. Pilih template lain.');
    const p = { id:uid('MR'), templateId:tid, templateVersion:s.catalog[tid].version, faceRegions:copy(s.catalog[tid].faces||template(tid).faces), createdAt:Date.now(), assignments:Array(template(tid).people).fill(null), sources:[], undo:[], versions:[], currentVersion:null, correctionUsed:0, failures:0, job:null, deleted:false };
    s.projects.unshift(p); log(s,'template_selected',{ project:p.id, template:tid }); return p;
  }
  function assign(s,p,slot,source,move=false) {
    if (p.deleted || activeJob(p) || p.versions.length) throw Error('Posisi wajah belum bisa diubah sekarang. Pakai koreksi di halaman hasil, ya.');
    if (!Number.isInteger(slot) || slot<0 || slot>=p.assignments.length) throw Error('Pilih posisi wajah yang tersedia.');
    if (source.expiresAt <= Date.now()) throw Error('Masa simpan foto aslinya habis. Upload ulang dan beri izin lagi, ya.');
    const other=p.assignments.findIndex(id=>id===source.id);
    if (other>=0 && other!==slot && !move) return other;
    p.undo.push([...p.assignments]);
    if (other>=0) p.assignments[other]=null;
    const existing=p.sources.find(x=>x.id===source.id);
    if(existing) Object.assign(existing,source); else p.sources.push(source);
    p.assignments[slot]=source.id;
    log(s,'reference_ready',{project:p.id,slot}); return -1;
  }
  function undoAssignment(p) {
    if (activeJob(p) || p.versions.length) throw Error('Pilih versi sebelumnya untuk memulihkan hasil.');
    if (p.undo.length) p.assignments=p.undo.pop().map(id=>p.sources.some(x=>x.id===id && x.expiresAt>Date.now())?id:null);
  }
  function changeTemplate(s,p,tid) {
    if(p.deleted || activeJob(p) || p.versions.length) throw Error('Template nggak bisa diganti setelah proses dimulai.');
    const t=template(tid),c=s.catalog[tid];
    if(!t || !c?.published) throw Error('Template ini sedang dijeda. Pilih template lain.');
    p.templateId=tid;p.templateVersion=c.version;p.faceRegions=copy(c.faces||t.faces);p.assignments=Array(t.people).fill(null);p.undo=[];
    log(s,'template_changed',{project:p.id,template:tid});
  }
  function admissionIssue(s,p,type='creation',now=Date.now()) {
    if (!p || p.deleted) return 'Proyek sudah dihapus.';
    if (activeJob(p)) return 'Proses masih berjalan. Cek status tanpa membuat permintaan baru.';
    if (!s.verified) return 'Masuk ke akun contoh sebelum membuat foto.';
    if (!s.controls.admission) return 'Pembuatan foto baru dijeda. Hasil dan download yang sudah ada tetap tersedia.';
    if (s.controls.outage) return 'Layanannya lagi bermasalah. Fotomu tetap tersimpan. Coba lagi nanti, ya.';
    if (!s.catalog[p.templateId]?.published) return 'Template sedang dijeda. Pilih template lain sebelum membuat foto.';
    if (p.failures>=s.controls.retries) return 'Batas percobaan teknis tercapai. Hubungi bantuan untuk pemulihan.';
    const running=s.projects.filter(x=>!x.deleted && activeJob(x));
    if (running.length>=s.controls.concurrency) return 'Antrean sedang penuh. Coba kembali setelah proses lain selesai.';
    const spent=s.events.filter(x=>['preview_ready','correction_completed'].includes(x.type)).length*s.controls.unitCost;
    if (spent+(running.length+1)*s.controls.unitCost>s.controls.budget) return 'Batas biaya uji tercapai. Pembuatan baru dijeda.';
    if (type==='creation') {
      if (s.creationsUsed || running.some(x=>x.job.type==='creation')) return 'Jatah satu pembuatan gratis sudah digunakan atau sedang diproses. Download lama tetap tersedia.';
      if (p.assignments.some(id=>!p.sources.some(x=>x.id===id && x.consentAt && x.expiresAt>now && x.src))) return 'Lengkapi semua wajah dan izin foto sebelum melanjutkan.';
    } else {
      if (!current(p)) return 'Bikin fotonya dulu, yuk.';
      if (p.correctionUsed) return 'Jatah koreksinya sudah dipakai. Kamu masih bisa pilih dan download hasil sebelumnya.';
      if (current(p).expiresAt<=now) return 'Hasil sudah kedaluwarsa.';
      if (current(p).refs.map(x=>p.renewedRefs?.[x.id]||x).some(x=>!x.src || x.expiresAt<=now)) return 'Foto asli kedaluwarsa. Perbarui foto dan izin untuk setiap wajah yang diperlukan.';
    }
    return '';
  }
  function startJob(s,p,type='creation',slot=null,replacement=null) {
    const issue=admissionIssue(s,p,type); if(issue) throw Error(issue);
    const refs=copy(type==='creation'?p.assignments.map(id=>p.sources.find(x=>x.id===id)):current(p).refs.map(x=>p.renewedRefs?.[x.id]||x));
    if(replacement) refs[slot]=copy(replacement);
    p.job={ id:uid('job'), type, slot, refs, templateVersion:p.templateVersion, faceRegions:copy(p.faceRegions), status:'queued', startedAt:Date.now(), readyAt:Date.now()+4200, parent:p.currentVersion, greeting:current(p)?.greeting||'' };
    log(s,type==='creation'?'creation_requested':'correction_requested',{project:p.id,job:p.job.id}); return p.job;
  }
  function finishJob(s,p,now=Date.now()) {
    if(p.deleted || !activeJob(p)) return false;
    const j=p.job;
    const v={ id:uid('v'), number:p.versions.length+1, templateId:p.templateId, refs:copy(j.refs), greeting:j.greeting, createdAt:now, expiresAt:now+30*DAY, kind:j.type, slot:j.slot, accepted:false, feedback:{} };
    p.versions.push(v);p.currentVersion=v.id;j.status='ready';
    if(j.type==='creation') s.creationsUsed+=1; else p.correctionUsed+=1;
    log(s,j.type==='creation'?'preview_ready':'correction_completed',{project:p.id,version:v.id});return true;
  }
  function tick(s,now=Date.now()) {
    let changed=false;
    for(const p of s.projects) {
      if(p.deleted) continue;
      for(const src of p.sources) if(src.src && src.expiresAt<=now) {src.src=null;changed=true;}
      for(const v of p.versions) for(const ref of v.refs) if(ref.src && ref.expiresAt<=now) {ref.src=null;changed=true;}
      for(const ref of [...Object.values(p.renewedRefs||{}),...(p.job?.refs||[])]) if(ref.src && ref.expiresAt<=now) {ref.src=null;changed=true;}
      if(!activeJob(p)) continue;
      if(s.controls.outage) {if(p.job.status!=='delayed'){p.job.status='delayed';changed=true;}continue;}
      if(p.job.status==='delayed'){p.job.status='processing';p.job.readyAt=now+2500;changed=true;}
      if(now>=p.job.readyAt) changed=finishJob(s,p,now)||changed;
      else if(now-p.job.startedAt>700 && p.job.status==='queued'){p.job.status='processing';changed=true;}
    }
    for(const o of s.orders) if(o.status==='pending' && o.expiresAt<=now){o.status='expired';changed=true;}
    return changed;
  }
  function failJob(s,p) {
    if(!activeJob(p)) return;
    p.job.status='failed';p.failures+=1;log(s,'job_failed',{project:p.id,job:p.job.id});
  }
  function greeting(s,p,text) {
    const old=current(p);
    if(!old || old.expiresAt<=Date.now() || activeJob(p)) throw Error('Pilih hasil aktif sebelum mengedit ucapan.');
    const normalized=text.trim();
    if([...normalized].length>48 || /[\x00-\x1f]/.test(normalized)) throw Error('Gunakan maksimal 48 karakter dalam satu baris.');
    if(normalized===old.greeting) return old;
    const v={...copy(old), id:uid('v'), number:p.versions.length+1, greeting:normalized, kind:'greeting', accepted:false, feedback:{}};
    p.versions.push(v);p.currentVersion=v.id;log(s,'greeting_saved',{project:p.id,version:v.id});return v;
  }
  function order(s,p) {
    const v=current(p);
    if(!v || v.expiresAt<=Date.now() || p.deleted || activeJob(p)) throw Error('Hasil ini belum siap dibeli atau sudah kedaluwarsa.');
    const existing=s.orders.find(o=>o.projectId===p.id && o.versionId===v.id && ['pending','paid','uncertain','refund_pending'].includes(o.status));
    if(existing) return existing;
    const o={id:uid('ORD'),projectId:p.id,versionId:v.id,versionNumber:v.number,templateId:v.templateId,status:'pending',amount:19900,currency:'IDR',createdAt:Date.now(),expiresAt:Date.now()+15*60000,resultExpiresAt:v.expiresAt};
    s.orders.unshift(o);log(s,'checkout_started',{project:p.id,order:o.id,version:v.id});return o;
  }
  function pay(s,o) {
    if(o.status==='paid') return;
    if(o.status!=='pending' || o.expiresAt<=Date.now()) throw Error('Pesanan tidak aktif. Cek status sebelum membuat pesanan baru.');
    const p=project(s,o.projectId), v=p?.versions.find(v=>v.id===o.versionId);
    if(!v || v.expiresAt<=Date.now()) throw Error('Versi ini tidak tersedia. Pembayaran diblokir.');
    o.status='paid';o.paidAt=Date.now();log(s,'payment_verified',{project:p.id,order:o.id,version:v.id});
  }
  function entitlement(s,p,v) {
    return !p.deleted && v.expiresAt>Date.now() && s.orders.some(o=>o.projectId===p.id && o.versionId===v.id && o.status==='paid');
  }
  function removeProject(s,p) {
    p.deleted=true;p.sources=[];p.assignments=[];p.undo=[];p.versions=[];p.currentVersion=null;p.renewedRefs={};
    if(p.job){p.job.status='cancelled';p.job.refs=[];}
    for(const o of s.orders.filter(o=>o.projectId===p.id)) {if(['pending','uncertain'].includes(o.status))o.status='cancelled';else if(o.status==='paid')o.status='refund_pending';}
    log(s,'deletion_completed',{project:p.id});
  }
  const api={DAY,templates,uid,copy,template,project,current,activeJob,initial,log,createProject,assign,undoAssignment,changeTemplate,admissionIssue,startJob,finishJob,tick,failJob,greeting,order,pay,entitlement,removeProject};
  root.Momenria=api;
  if(typeof module!=='undefined') module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
