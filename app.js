(function () {
  'use strict';
  const M=window.Momenria, $=s=>document.querySelector(s);
  const paths={arrow:'M4 12h16m-6-6 6 6-6 6',back:'M20 12H4m6-6-6 6 6 6',chevron:'m9 5 7 7-7 7',check:'m5 12 4 4L19 6',close:'m6 6 12 12M6 18 18 6',plus:'M12 5v14M5 12h14',menu:'M4 6h16M4 12h16M4 18h16',upload:'M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5',download:'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3zm-4 9 3 3 5-6',image:'M3 3h18v18H3zM3 17l6-6 4 4 3-3 5 5M7 7h.01',users:'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M2 21v-3a7 7 0 0 1 14 0v3M17 3a4 4 0 0 1 0 8m2 4a5 5 0 0 1 3 5',home:'m3 11 9-8 9 8v10h-6v-7H9v7H3z',spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',lock:'M6 10h12v11H6zM8 10V6a4 4 0 0 1 8 0v4',undo:'M4 10h10a6 6 0 0 1 0 12M4 10l5-5m-5 5 5 5',zoom:'M16 16l5 5M10 5v10M5 10h10M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',info:'M12 11v6m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',receipt:'M5 3h14v18l-3-2-4 2-4-2-3 2zM8 7h8M8 11h8M8 15h4',help:'M8 8a4 4 0 0 1 8 0c0 3-4 3-4 6m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',settings:'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-8 0v6',play:'m9 5 11 7-11 7z',heart:'M20 5c-3-3-6-1-8 1-2-2-5-4-8-1-5 5 8 15 8 15S25 10 20 5',refresh:'M20 7v6h-6M4 17v-6h6M20 12a8 8 0 0 0-14-6M4 12a8 8 0 0 0 14 6'};
  const icon=name=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.image}"/></svg>`;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date=value=>new Intl.DateTimeFormat('id-ID',{day:'numeric',month:'long',year:'numeric'}).format(new Date(value));
  const money=value=>'Rp'+new Intl.NumberFormat('id-ID').format(value);
  const statusNames={pending:'Menunggu pembayaran',paid:'Lunas · mode uji',failed:'Gagal',expired:'Kedaluwarsa',uncertain:'Perlu pemeriksaan',refund_pending:'Pengembalian diproses',refunded:'Dana dikembalikan',cancelled:'Dibatalkan',queued:'Menunggu giliran',processing:'Foto sedang dibuat',delayed:'Proses tertunda',ready:'Selesai',waiting:'Menunggu',action_required:'Perlu tindakan',resolved:'Selesai'};
  let state=M.initial(), db=null, memoryOnly=false, selectedFace=0, occasion='Semua', count='all', uploadContext=null, uploadSerial=0, toastTimer, modalReturn=null, lastRoute='', scrollPositions={}, pageLimit=24;
  const imagePromises=new Map(), sampleResults=new Map();
  let portraitBundle=null, studioTemplateId='studio';
  const route=()=>location.hash.replace(/^#/, '')||'/';
  const brand=()=>`<a class="brand" href="#/" aria-label="MomenRia, studio foto"><svg class="brand-symbol" viewBox="0 0 32 32" aria-hidden="true"><path d="M15 15C5 15 2 10 4 6s9-4 11 9ZM17 15c0-10 5-13 9-11s4 9-9 11ZM17 17c10 0 13 5 11 9s-9 4-11-9ZM15 17c0 10-5 13-9 11s-4-9 9-11Z"/></svg>MomenRia<span class="sr-only"> — potret keluarga</span></a>`;
  const photo=(t,cls='',extra='')=>`<img class="od-media ${cls}" src="${t.image}" width="1448" height="1086" alt="Contoh ilustrasi AI ${esc(t.name)}, ${t.people} orang" ${extra}>`;
  function faceCrop(t,index) {
    const [x,y]=t.faces[index], side=250;
    return `<span class="face-crop"><svg viewBox="${Math.round(x*1448-side/2)} ${Math.round(y*1086-side/2)} ${side} ${side}" role="img" aria-label="Contoh wajah ${index+1}"><image href="${t.image}" width="1448" height="1086"/></svg></span>`;
  }
  function header() {
    return `<div class="app-topbar">${brand()}<div class="app-product-name">Studio foto keluarga</div><div class="app-account"><span class="local-badge">${icon('shield')}Tersimpan di browser ini</span><a class="app-price-link" href="#/pricing">Harga download</a><button class="btn secondary small" data-action="account">${icon('users')}${state.verified?'Akun saya':'Masuk'}</button><button class="icon-btn app-mobile-menu" data-action="menu" aria-label="Menu aplikasi">${icon('menu')}</button></div></div>`;
  }
  function appNavigation() {
    const section=route().split('/')[1],studio=['','templates','editor','new'].includes(section);
    const links=[['/','spark','Studio',studio],['/projects','image','Foto saya',section==='projects'],['/orders','receipt','Pesanan',['orders','order'].includes(section)],['/support','help','Bantuan',['support','how'].includes(section)]];
    return `<nav class="app-nav-main" aria-label="Navigasi aplikasi">${links.map(([url,i,label,active])=>`<a class="app-nav-link ${active?'active':''}" href="#${url}" ${active?'aria-current="page"':''}>${icon(i)}<span>${label}</span></a>`).join('')}</nav><nav class="app-nav-secondary" aria-label="Pengaturan"><a class="app-nav-link ${section==='privacy'?'active':''}" href="#/privacy" ${section==='privacy'?'aria-current="page"':''}>${icon('shield')}<span>Privasi</span></a><a class="app-nav-link ${section==='operator'?'active':''}" href="#/operator" ${section==='operator'?'aria-current="page"':''}>${icon('settings')}<span>Pengelola</span></a></nav>`;
  }
  function studioDraft() {
    return state.projects.find(p=>!p.deleted&&!p.versions.length)||null;
  }
  function studioTemplate(p=null) {
    return p?M.template(p.templateId):M.templates.find(t=>t.id===studioTemplateId&&state.catalog[t.id].published)||M.templates.find(t=>state.catalog[t.id].published)||M.templates[0];
  }
  function templateCards(p=null) {
    const selected=studioTemplate(p);
    return M.templates.map(t=>`<button class="studio-template od-tile ${t.id===selected.id?'selected':''}" data-action="studio-template" data-template="${t.id}" data-project="${p?.id||''}" aria-pressed="${t.id===selected.id}" aria-label="${esc(t.name)}, ${t.people} orang${state.catalog[t.id].published?'':', dijeda'}" ${state.catalog[t.id].published?'':'disabled'}><span class="studio-template-image">${photo(t)}${t.id===selected.id?`<span class="template-selected">${icon('check')}</span>`:''}</span><span class="od-field"><strong>${t.occasion}</strong><span>${t.people} orang${state.catalog[t.id].published?'':' · Dijeda'}</span></span></button>`).join('');
  }
  function homeView() {
    const p=studioDraft();
    return p?editorView(p):studioView();
  }
  function studioView(p=null) {
    const t=studioTemplate(p),ready=p?p.assignments.filter(id=>p.sources.some(s=>s.id===id&&s.src&&s.expiresAt>Date.now())).length:0;
    const issue=p?M.admissionIssue(state,p):state.catalog[t.id].published?'Tambahkan foto untuk setiap wajah.':'Semua template sedang dijeda.';
    const preview=p||{id:'',templateId:t.id,faceRegions:state.catalog[t.id].faces||t.faces,assignments:Array(t.people).fill(null),versions:[],currentVersion:null};
    return `<section class="studio" aria-labelledby="studio-title"><div class="studio-toolbar"><div class="od-field"><h1 id="studio-title">Foto keluarga AI</h1><p>Pilih suasananya, lalu ajak orang tersayang masuk foto.</p></div><div class="od-row studio-toolbar-actions"><span class="draft-status">${icon(p?'check':'image')}${p?(memoryOnly?'Draf sementara':'Draf tersimpan'):'Proyek baru'}</span><button class="icon-btn" data-action="new-studio" aria-label="Buat proyek baru">${icon('plus')}</button><a class="icon-btn" href="#/how" aria-label="Panduan membuat foto">${icon('help')}</a></div></div><div class="studio-grid"><aside class="studio-controls" aria-label="Pengaturan foto"><section><div class="control-heading"><h2><span class="control-number">01</span>Pilih template</h2><span class="control-meta">3 suasana</span></div><div class="studio-templates">${templateCards(p)}</div></section><section><div class="control-heading"><h2><span class="control-number">02</span>Tambahkan foto</h2><span class="upload-count">${ready}/${t.people}</span></div><p class="control-description">Satu foto yang jelas buat tiap orang, ya.</p><div class="studio-uploads">${t.faces.map((_,i)=>{const source=p?.sources.find(s=>s.id===p.assignments[i]&&s.src&&s.expiresAt>Date.now());return `<button class="upload-tile ${source?'ready':''} ${selectedFace===i&&p?'selected':''}" data-action="studio-face" data-project="${p?.id||''}" data-slot="${i}" aria-label="${source?'Ganti':'Tambahkan'} foto untuk wajah ${i+1}" ${state.catalog[t.id].published||p?'':'disabled'}><span class="upload-tile-top">${source?`<img src="${esc(source.src)}" alt="Foto referensi wajah ${i+1}" width="48" height="48">`:icon('plus')}<span class="upload-slot">${i+1}</span></span><span class="od-field"><strong>Wajah ${i+1}</strong><span>${source?'Foto siap · Ganti':'Pilih foto'}</span></span></button>`;}).join('')}</div><p class="upload-format">JPG / PNG · Maks. 10 MB per foto</p>${p?.undo.length?`<button class="link-btn studio-undo" data-action="undo-draft" data-project="${p.id}">${icon('undo')}Urungkan penempatan</button>`:''}</section><div class="studio-submit"><div class="allowance">${icon('spark')}1 kali bikin foto + 1 kali koreksi</div><button class="btn primary block" data-action="generate" data-project="${p?.id||''}" ${issue?'disabled':''}>${icon('spark')}Buat foto${icon('arrow')}</button><p class="generation-hint" role="status">${issue?esc(issue):'Semua wajah siap. Buat foto sekarang.'}</p><span class="studio-price">Preview gratis <span aria-hidden="true">·</span> <a href="#/pricing">HD Rp19.900</a></span></div></aside><div class="studio-preview"><div class="preview-heading"><span class="od-row">${icon('image')}Preview template</span><span class="preview-format">4:3 <span>·</span> ${t.people} orang</span></div>${canvas(preview)}<div class="studio-stage-note"><span class="tag">Contoh AI</span><p>Pose, pakaian, dan suasananya ikut template.<br>Ketuk nomor untuk memasangkan foto wajah.</p></div><div class="studio-simulation">${icon('info')}Ini simulasi, ya. Hasilnya masih pakai gambar contoh.</div></div></div></section>`;
  }
  function openStudioFace(p,slot) {
    const existing=p||studioDraft();
    const draft=existing||M.createProject(state,studioTemplate().id);
    selectedFace=slot;
    if(!existing)persist();
    history.replaceState(null,'','#/editor/'+draft.id);
    render(true);
    return picker(draft,slot);
  }
  function guideView(pricing=false) {
    return `<section class="wrap page guide-page"><div class="page-header"><div><h1>${pricing?'Pilihan download':'Panduan studio'}</h1><p>${pricing?'Cek hasilnya dulu, lalu pilih versi yang mau kamu simpan.':'Tiga langkah buat bikin foto bareng.'}</p></div><a class="btn secondary" href="#/">Kembali ke studio ${icon('arrow')}</a></div>${pricing?`<div class="download-options"><article class="op-card"><span class="tag">Preview</span><h2>Gratis</h2><ul class="feature-list"><li>${icon('check')}Contoh 768 × 576 px</li><li>${icon('check')}Dengan watermark MomenRia</li><li>${icon('check')}1 kali bikin foto + 1 kali koreksi</li></ul></article><article class="op-card"><span class="tag">Resolusi tinggi</span><h2>Rp19.900 <small>/ foto</small></h2><ul class="feature-list"><li>${icon('check')}Contoh 2048 × 1536 px</li><li>${icon('check')}Tanpa watermark MomenRia</li><li>${icon('check')}Download versi yang sama selama masa simpan 30 hari</li></ul></article></div><div class="notice">Harga penawaran uji. QRIS disimulasikan dan tidak menagih uang. Download merupakan gambar contoh yang diperbesar dari 1448 × 1086 px, bukan personalisasi foto upload.</div>`:`<div class="guide-steps">${[['01','Pilih template','Pilih suasana buat dua, tiga, atau empat orang. Posisi, pakaian, dan latarnya ikut template.'],['02','Tambahkan foto','Ketuk nomor di foto atau kotak wajahnya. Siapkan satu foto yang jelas dan sudah diizinkan buat tiap orang.'],['03','Buat dan cek','Cek tiap wajah. Kalau perlu, pakai satu kali koreksi untuk satu wajah per proyek. Lalu download preview atau pilih resolusi tinggi.']].map(([n,title,copy])=>`<article class="op-card od-row-top"><span class="control-number">${n}</span><div class="od-field"><h2>${title}</h2><p>${copy}</p></div></article>`).join('')}</div><div class="notice">Foto tetap di browser ini. AI, akun, dan pembayaran disimulasikan. Hasil contoh tidak menggunakan wajah upload.</div><div class="guide-links"><a href="#/privacy">Privasi dan masa simpan</a><a href="#/pricing">Pilihan download</a><a href="#/support">Bantuan</a></div>`}</section>`;
  }
  const crumbs=text=>`<a class="back-link" href="#/projects">${icon('back')}Foto saya</a><span class="muted small-copy"> / ${text}</span>`;
  const steps=active=>`<div class="steps" aria-label="Tahapan pembuatan">${['Pilih template','Tambahkan foto','Cek hasil'].map((x,i)=>`${i?'<i class="step-line" aria-hidden="true"></i>':''}<span class="${i===active?'active':''}"><span class="step-number">${i<active?'✓':i+1}</span>${x}</span>`).join('')}</div>`;
  function faceList(p,isResult=false) {
    const t=M.template(p.templateId),v=M.current(p);
    return `<div class="face-list">${t.faces.map((_,i)=>{const s=isResult?v.refs[i]:p.sources.find(x=>x.id===p.assignments[i]);return `<button class="face-row ${selectedFace===i?'selected':''}" data-action="face" data-project="${p.id}" data-slot="${i}" aria-pressed="${selectedFace===i}">${s?.src?`<img class="source-thumb" src="${esc(s.src)}" alt="Foto referensi wajah ${i+1}" width="44" height="44">`:`<span class="face-placeholder">${i+1}</span>`}<span class="od-field"><b>Wajah ${i+1}</b><small>${s?.src?'Foto siap':s?'Sumber kedaluwarsa':'Tambahkan foto'}</small></span>${icon(s?.src?'check':'plus')}</button>`;}).join('')}</div>`;
  }
  function canvas(p,result=false,markers=true) {
    const t=M.template(p.templateId),v=M.current(p);
    return `<div class="canvas-panel"><div class="canvas-tools"><span>${result?'Hasil pilihan · Versi '+v.number:'Template · '+t.name}</span><div class="od-row">${result?`<button class="icon-btn" data-action="zoom" data-project="${p.id}" aria-label="Perbesar hasil">${icon('zoom')}</button>`:`<button class="icon-btn" data-action="template-preview" data-template="${t.id}" aria-label="Lihat template ${esc(t.name)}">${icon('zoom')}</button>`}</div></div><div class="canvas-wrap"><div class="portrait-canvas">${result?`<img class="od-media result-preview" data-preview="${p.id}:${v.id}" src="${t.image}" alt="Preview contoh versi ${v.number}; bukan hasil dari foto upload" width="768" height="576">`:photo(t)}${markers?(p.faceRegions||t.faces).map(([x,y],i)=>`<button class="face-target ${p.assignments[i]?'ready':''}" style="--x:${x*100}%;--y:${y*100}%" aria-label="Wajah ${i+1}, ${result?'cek hasil':p.assignments[i]?'foto siap':'tambahkan foto'}" aria-pressed="${Boolean(p.id)&&selectedFace===i}" data-action="${result?'face':'studio-face'}" data-project="${p.id}" data-slot="${i}"><span class="number">${i+1}</span></button>`).join(''):''}</div><div class="canvas-caption"><p>${result?'Contoh hasil AI · Bukan personalisasi upload':'Ketuk salah satu wajah untuk menambahkan foto.'}</p><span class="tag">${t.people} orang</span></div></div><div class="canvas-hint">${icon('shield')}<span>Foto hanya tersimpan di browser ini. Tidak dikirim ke layanan AI.</span></div></div>`;
  }
  function editorView(p) {
    if(M.activeJob(p)||p.job?.status==='failed')return processingView(p);
    if(p.versions.length)return resultView(p);
    return studioView(p);
  }
  function processingView(p) {
    const j=p.job,failed=j.status==='failed',delayed=j.status==='delayed';
    return `<section class="wrap page editor-page"><div class="breadcrumb">${crumbs('Pembuatan foto')}</div>${steps(2)}<div class="page-header"><div><h1>${failed?'Fotonya belum berhasil dibuat.':delayed?'Prosesnya agak lama, ya.':'Lagi bikin fotomu.'}</h1><p>${failed?'Foto asli dan hasil sebelumnya tetap tersimpan.':delayed?'Jangan membuat permintaan baru. Cek status untuk proses yang sama.':'Kamu boleh meninggalkan halaman ini dan kembali ke Foto saya.'}</p></div><span class="tag">${statusNames[j.status]}</span></div><div class="editor-layout">${canvas(p,false,false)}<aside class="side-panel"><span class="tag mb16">Proses simulasi</span><h2>${statusNames[j.status]}</h2>${!failed&&!delayed?'<div class="loading-bar" role="progressbar" aria-label="Pembuatan contoh sedang berlangsung"></div>':''}<ol class="progress-steps"><li><span class="progress-dot done">✓</span>Foto dan posisi tersimpan</li><li><span class="progress-dot ${j.status==='processing'?'running':''}">2</span>Menyusun contoh potret</li><li><span class="progress-dot">3</span>Menyiapkan preview</li></ol><p class="notice">${failed?'Proses uji dihentikan. Jatah tidak terpakai karena belum ada hasil yang selesai.':delayed?'Gangguan layanan uji. Status akan dilanjutkan saat pengelola memulihkan layanan.':'Tidak ada upload ke layanan AI. Preview akan menampilkan contoh, bukan wajah dari upload.'}</p><div class="panel-actions">${failed?`<button class="btn primary" data-action="retry-job" data-project="${p.id}">Coba lagi ${icon('refresh')}</button>`:`<button class="btn secondary" data-action="check-job" data-project="${p.id}">Cek status ${icon('refresh')}</button>`}<button class="link-btn" data-action="support" data-project="${p.id}">Butuh bantuan?</button>${p.versions.length?`<button class="link-btn" data-action="previous-result" data-project="${p.id}">Lihat hasil sebelumnya</button>`:''}</div></aside></div></section>`;
  }
  function resultView(p,force=false) {
    if(M.activeJob(p)&&!force)return processingView(p);
    const v=M.current(p);if(!v)return editorView(p);
    const paid=M.entitlement(state,p,v),expired=v.expiresAt<=Date.now();
    if(expired)return `<section class="wrap page editor-page"><div class="page-header"><div><h1>Masa simpan sudah berakhir.</h1><p>Hasil versi ${v.number} kedaluwarsa pada ${date(v.expiresAt)}. Download dan koreksi tidak tersedia.</p></div></div><button class="btn secondary" data-action="support" data-project="${p.id}">Hubungi bantuan</button></section>`;
    return `<section class="wrap page editor-page"><div class="breadcrumb">${crumbs('Hasil foto')}</div>${steps(2)}<div class="page-header"><div><h1>Yuk, cek hasil fotomu</h1><p>Cek wajahnya satu-satu, lalu pilih hasil yang kamu suka.</p></div><span class="tag">${paid?'Sudah dibeli · mode uji':'Versi '+v.number}</span></div><div class="editor-layout"><div>${canvas(p,true)}<div class="result-actions"><button class="btn secondary small" data-action="greeting" data-project="${p.id}">Tambah ucapan</button><button class="link-btn" data-action="zoom" data-project="${p.id}">${icon('zoom')}Lihat seluruh foto</button></div><div class="version-select"><label for="version">Riwayat hasil</label><select id="version" class="input" data-project="${p.id}">${p.versions.map(x=>`<option value="${x.id}" ${x.id===v.id?'selected':''}>Versi ${x.number} · ${x.kind==='greeting'?'Ucapan baru':x.kind==='correction'?'Koreksi contoh':'Hasil pertama'}${M.entitlement(state,p,x)?' · Sudah dibeli':''}</option>`).join('')}</select><p class="fine mt16">Kamu bisa pilih versi sebelumnya, tapi jatah koreksi nggak kembali, ya. Pembelian tetap untuk versi yang sudah kamu pilih.</p></div></div><aside class="side-panel"><h2>Wajahnya sudah cocok?</h2><p>Ketuk wajah untuk membandingkan foto atau memberi masukan.</p>${faceList(p,true)}<label class="check"><input type="checkbox" id="accept-faces" data-project="${p.id}" ${v.accepted?'checked':''}><span>Semua wajah sudah sesuai</span></label><p class="fine">Memberi masukan nggak berarti membeli. Contoh AI ini juga belum mengukur kemiripan fotomu.</p><div class="panel-actions"><button class="btn primary block" data-action="${paid?'download-paid':'checkout'}" data-project="${p.id}">${paid?'Download resolusi tinggi':'Beli foto · Rp19.900'}${icon(paid?'download':'arrow')}</button><button class="btn secondary block" data-action="download-free" data-project="${p.id}">${icon('download')}Download gratis</button><p class="state-note">Gratis: 768 px dengan watermark<br>Resolusi tinggi: 2048 × 1536 px · Contoh</p></div><div class="notice mt24">${p.correctionUsed?'Koreksi bersama sudah digunakan.':'Ada 1 kali koreksi untuk 1 wajah di proyek ini.'}</div><p class="fine mt16">Hasil tersedia hingga ${date(v.expiresAt)}. Tidak diperpanjang saat membeli atau download.</p></aside></div></section>`;
  }
  function projectsView(orders=false) {
    const list=state.projects.filter(p=>!p.deleted);
    return `<section class="wrap page"><div class="page-header"><div><div class="eyebrow">Ruang kenanganmu</div><h1>Foto saya</h1><p>Lanjutkan momen yang tersimpan di browser ini.</p></div><a class="btn primary" href="#/templates">Buat momen ${icon('plus')}</a></div><nav class="page-tabs" aria-label="Koleksi pribadi"><a class="${!orders?'active':''}" href="#/projects">Proyek (${list.length})</a><a class="${orders?'active':''}" href="#/orders">Pesanan (${state.orders.length})</a><a href="#/support">Bantuan saya</a></nav>${orders?ordersList():!list.length?`<div class="empty">${icon('image')}<h2>Cerita pertama dimulai di sini.</h2><p>Belum ada foto tersimpan. Pilih template untuk membuat potret keluarga pertamamu.</p><a class="btn secondary" href="#/templates">Temukan template ${icon('arrow')}</a></div>`:`<div class="list">${list.slice(0,pageLimit).map(p=>{const t=M.template(p.templateId),v=M.current(p);return `<article class="project-card">${photo(t)}<div><h3>${t.name}</h3><span class="tag">${M.activeJob(p)?statusNames[p.job.status]:v?'Hasil siap · v'+v.number:'Draf · '+p.assignments.filter(Boolean).length+'/'+t.people+' wajah'}</span><div class="card-meta"><span>${p.id}</span><span>${date(p.createdAt)}</span>${v?`<span>Tersedia hingga ${date(v.expiresAt)}</span>`:''}</div></div><div class="card-actions"><button class="icon-btn" aria-label="Hapus proyek ${p.id}" data-action="delete" data-project="${p.id}">${icon('trash')}</button><a class="btn secondary small" href="#/editor/${p.id}">${v?'Lihat hasil':'Lanjutkan'}${icon('arrow')}</a></div></article>`;}).join('')}</div>${list.length>pageLimit?'<button class="btn secondary mt24" data-action="load-more">Tampilkan lebih banyak</button>':''}`}<p class="fine mt24">Akun contoh tersimpan lokal. Menghapus data browser juga menghapus akses ke proyek ini.</p></section>`;
  }
  function ordersList() {
    return state.orders.length?`<div class="list">${state.orders.slice(0,pageLimit).map(o=>`<article class="project-card">${photo(M.template(o.templateId))}<div><h3>${M.template(o.templateId).name}</h3><span class="tag">${statusNames[o.status]}</span><div class="card-meta"><span>${o.id}</span><span>Versi ${o.versionNumber} · ${money(o.amount)}</span><span>${date(o.createdAt)}</span></div></div><a class="btn secondary small" href="#/order/${o.id}">Lihat pesanan ${icon('arrow')}</a></article>`).join('')}</div>${state.orders.length>pageLimit?'<button class="btn secondary mt24" data-action="load-more">Tampilkan lebih banyak</button>':''}`:`<div class="empty">${icon('receipt')}<h2>Belum ada pesanan</h2><p>Cek hasil fotonya dulu, ya. Pesanan muncul setelah kamu pilih resolusi tinggi.</p><a class="btn secondary" href="#/projects">Kembali ke foto saya</a></div>`;
  }
  function orderView(o) {
    const p=M.project(state,o.projectId),v=p?.versions.find(v=>v.id===o.versionId),active=v&&v.expiresAt>Date.now(),paid=o.status==='paid';
    return `<section class="wrap page"><a class="back-link" href="#/orders">${icon('back')}Semua pesanan</a><div class="page-header"><div><h1>${paid?'Momennya siap disimpan.':'Simpan versi pilihanmu.'}</h1><p>Pesanan ${o.id} · ${statusNames[o.status]}</p></div></div><div class="checkout-layout"><div><figure class="photo-frame">${active?`<img class="od-media result-preview" data-preview="${p.id}:${v.id}" src="${M.template(o.templateId).image}" width="768" height="576" alt="Versi ${o.versionNumber} yang terikat pada pesanan">`:`<div class="image-empty">${icon('image')}Hasil dihapus atau kedaluwarsa.<br>Foto nggak bisa didownload.</div>`}<figcaption class="image-caption"><span class="caption-title">${M.template(o.templateId).name}</span><span>VERSI ${o.versionNumber}</span></figcaption></figure><p class="fine mt16">Pembayaran membuka versi ini, tanpa membuat foto baru. Perubahan di editor tidak mengganti foto dalam pesanan ini.</p><p class="fine mt16">Contoh AI 2048 × 1536 px, diperbesar dari ilustrasi 1448 × 1086 px. Tidak mewakili hasil personalisasi atau kualitas layanan produksi.</p></div><div class="checkout-panel">${paid?`<div class="success-mark">${icon('check')}</div><h2>Pembayaran uji berhasil</h2><p class="small-copy muted">Nggak ada uang yang ditagih. Contoh resolusi tinggi sudah bisa kamu buka.</p>`:`<h2>Ringkasan pesanan</h2><span class="tag">QRIS · mode uji</span>`}<div class="order-rows"><div class="order-row"><span>Foto pilihan</span><b>Versi ${o.versionNumber}</b></div><div class="order-row"><span>Resolusi contoh</span><b>2048 × 1536 px</b></div><div class="order-row"><span>Batas download</span><b>${date(o.resultExpiresAt)}</b></div><div class="order-row total"><span>Total</span><b>${money(o.amount)}</b></div></div>${paid&&active?`<button class="btn primary block" data-action="download-order" data-order="${o.id}">${icon('download')}Download foto pilihan</button><p class="fine mt16">Download ulang versi ini tanpa pembelian tambahan selama masa simpan.</p>`:o.status==='pending'&&active?`<div class="notice">Mode pembayaran uji. Tidak ada kode QR aktif atau perpindahan ke dompet. Tombol di bawah menyimulasikan verifikasi pembayaran.</div><div class="payment-stamp">${icon('receipt')}<div class="od-field"><b>QRIS</b><small class="muted">Simulasi, bukan tagihan</small></div></div><p class="fine mt16">Penawaran berlaku hingga ${new Date(o.expiresAt).toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'})}. Harga tetap Rp19.900 untuk pesanan ini.</p><button class="btn primary block mt24" data-action="pay" data-order="${o.id}">Bayar di mode uji ${icon('arrow')}</button><button class="link-btn block" data-action="check-payment" data-order="${o.id}">Cek pembayaran</button>`:`<div class="notice">${o.status==='refund_pending'?'Permintaan pengembalian sedang dicek. Tidak ada transaksi uang nyata.':o.status==='refunded'?'Pengembalian dana uji telah dicatat.':o.status==='uncertain'?'Status perlu dicek pengelola. Download tetap terkunci sampai status selesai.':'Pesanan tidak aktif. Tidak ada pembayaran yang akan dilakukan.'}</div>${['expired','failed'].includes(o.status)&&active?`<button class="btn primary block mt24" data-action="reorder" data-order="${o.id}">Buat pesanan baru</button>`:''}`}<button class="link-btn block mt16" data-action="support" data-project="${o.projectId}" data-order="${o.id}">Ada kendala? Hubungi bantuan</button><p class="fine mt16">Kalau versi yang kamu beli nggak bisa dikirim, minta bantuan untuk memulihkan foto atau mengembalikan dana. Berubah selera bukan kegagalan pengiriman, ya. Jam layanan publik belum ditetapkan.</p></div></div></section>`;
  }
  function privacyView() {
    return `<section class="wrap page privacy-page"><a class="back-link" href="#/">${icon('back')}Studio</a><h1 class="mt16">Privasi foto</h1><p class="mt24">Di demo ini, foto dan proyekmu cuma disimpan di browser yang kamu pakai. Fotonya nggak dikirim ke server atau layanan AI.</p><h2>Izin untuk setiap foto</h2><p>Pakai foto milikmu atau yang sudah kamu punya izin untuk gunakan. Untuk foto anak, pastikan ada izin dari wali yang berwenang, ya. Kamu tidak perlu mengisi nama, usia, hubungan keluarga, atau profil orang dalam foto.</p><h2>Masa simpan yang jelas</h2><ul><li>Foto asli: 7 hari sejak ditambahkan.</li><li>Hasil contoh: 30 hari sejak selesai.</li><li>Membeli, membuka, dan download tidak memperpanjang masa simpan.</li></ul><p>Tanggal berakhir ditampilkan di proyek dan pesanan. Di prototipe lokal, pembersihan dicek ketika aplikasi dibuka. Data tidak dibersihkan oleh server saat browser tertutup.</p><h2>Hapus lebih awal</h2><p>Hapus proyek melalui Foto saya. Akses foto, proses, koreksi, dan download berakhir; catatan pesanan uji tetap tersedia untuk penyelesaian status. Foto tidak dipublikasikan, digunakan untuk pemasaran, atau dikirim untuk pelatihan.</p><h2>Batas prototipe</h2><p>Akun dan hak download hanya simulasi lokal, bukan perlindungan server. Jangan gunakan prototipe sebagai penyimpanan utama. Hasil AI adalah ilustrasi fiktif; penyedia pemrosesan, kebijakan produksi, dan prosedur wali belum dipilih.</p><a href="#/projects" class="btn secondary">Kelola foto saya ${icon('arrow')}</a></section>`;
  }
  function supportView() {
    return `<section class="wrap page"><div class="page-header"><div><h1>Bantuan saya</h1><p>Permintaan dan balasan contoh tersimpan di browser ini.</p></div><button class="btn primary" data-action="support">Tulis permintaan ${icon('plus')}</button></div>${state.tickets.length?state.tickets.slice(0,pageLimit).map(t=>`<article class="op-card"><div class="row"><h3>${esc(t.subject)}</h3><span class="tag">${statusNames[t.status]}</span></div><p class="full-detail">${esc(t.message)}</p><div class="op-meta">${t.id} · ${date(t.at)}${t.project?' · '+esc(t.project):''}${t.order?' · '+esc(t.order):''}</div>${t.reply?`<div class="notice"><strong>Balasan pengelola</strong>${esc(t.reply)}</div>`:''}</article>`).join(''):`<div class="empty">${icon('help')}<h2>Belum ada permintaan</h2><p>Kalau bikin atau download foto terkendala, kirim pesan dari halaman proyek atau pesanan. Detailnya ikut tercatat supaya lebih mudah dicek.</p><a class="btn secondary" href="#/projects">Lihat foto saya</a></div>`}<p class="fine mt24">Tidak ada pesan yang dikirim ke pihak lain. Jam layanan produksi belum ditetapkan.</p></section>`;
  }
  function operatorView(tab='overview') {
    const links=[['overview','Ringkasan','grid'],['catalog','Template','image'],['jobs','Proses','clock'],['orders','Pesanan','receipt'],['support','Bantuan','help'],['settings','Pengaturan','settings']];
    const readyEvents=state.events.filter(e=>['preview_ready','correction_completed'].includes(e.type)),paid=state.orders.filter(o=>o.status==='paid');
    let content='';
    if(tab==='overview')content=`<h2>Operasional hari ini</h2><div class="stats"><div class="stat od-stat"><strong>${state.projects.filter(p=>!p.deleted).length}</strong><span>Proyek di browser ini</span></div><div class="stat od-stat"><strong>${paid.length}</strong><span>Pesanan lunas uji</span></div><div class="stat od-stat"><strong>${money(readyEvents.length*state.controls.unitCost)}</strong><span>Estimasi biaya simulasi</span></div></div><div class="op-card"><h3>Validasi sebelum rilis</h3><p>Deteksi wajah, kemiripan, izin penyedia, QRIS, dan kontrol akses server belum divalidasi. Angka di sini hanya berasal dari penggunaan prototipe; bukan bukti kelayakan publik.</p><div class="support-status"><span class="tag outline">Evaluasi kemiripan: belum tersedia</span><span class="tag outline">Biaya aktual: belum tersedia</span></div></div><div class="op-card"><h3>Aktivitas terbaru</h3>${state.events.length?`<ul class="audit-list">${state.events.slice(0,24).map(e=>`<li><span>${esc(e.type)}${e.project?' · '+esc(e.project):''}</span><time>${new Date(e.at).toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'})}</time></li>`).join('')}</ul>`:'<p>Belum ada aktivitas. Mulai dari katalog untuk menjalankan alur pelanggan.</p>'}</div>`;
    if(tab==='catalog')content=`<h2>Katalog template</h2>${M.templates.map(t=>{const c=state.catalog[t.id];return `<article class="op-card"><div class="row"><div><h3>${t.name}</h3><p>${t.people} posisi · Versi konfigurasi ${c.version} · ${t.attire}</p></div><span class="tag">${c.published?'Terbit · contoh':'Dijeda'}</span></div><p class="op-meta">Wilayah wajah ${c.regions?'lengkap':'perlu ditinjau'} · Bukti kelayakan ${c.evidence?'contoh tersedia':'belum ditandai'} · Aset fiktif AI</p><div class="actions"><button class="btn secondary small" data-action="toggle-template" data-template="${t.id}">${c.published?'Jeda template':'Terbitkan contoh'}</button><button class="btn secondary small" data-action="regions" data-template="${t.id}">Tinjau wilayah</button><button class="link-btn" data-action="evidence" data-template="${t.id}">${c.evidence?'Batalkan tanda contoh':'Tandai evaluasi contoh'}</button></div></article>`;}).join('')}<p class="fine">Perubahan konfigurasi membuat versi baru. Proyek lama menyimpan wilayah yang dipilih; gambar yang sudah dibeli tidak berubah. Publikasi di sini hanya untuk katalog prototipe.</p>`;
    if(tab==='jobs')content=`<h2>Proses & pemulihan</h2>${state.projects.some(p=>p.job)?state.projects.filter(p=>p.job).slice(0,pageLimit).map(p=>`<article class="op-card"><div class="row"><div><h3>${M.template(p.templateId).name}</h3><p>${p.id} · ${p.job.id}</p></div><span class="tag">${statusNames[p.job.status]}</span></div><p class="op-meta">${p.deleted?'Proyek dihapus; hasil terlambat dibuang.':p.job.type==='creation'?'Pembuatan awal':'Koreksi'} · Percobaan gagal: ${p.failures}</p><div class="actions">${M.activeJob(p)?`<button class="btn secondary small" data-action="fail-job" data-project="${p.id}">Catat gagal teknis</button>`:''}${!p.deleted&&p.job.status==='failed'?`<button class="btn secondary small" data-action="allow-retry" data-project="${p.id}">Izinkan coba ulang</button>`:''}${!p.deleted?`<a class="link-btn" href="#/editor/${p.id}">Buka status pelanggan ${icon('arrow')}</a>`:''}</div></article>`).join(''):'<div class="empty"><h3>Belum ada proses</h3><p>Permintaan pembuatan dan koreksi muncul di sini.</p></div>'}`;
    if(tab==='orders')content=`<h2>Pesanan & pengembalian</h2>${state.orders.length?state.orders.slice(0,pageLimit).map(o=>`<article class="op-card"><div class="row"><div><h3>${o.id}</h3><p>Versi ${o.versionNumber} · ${money(o.amount)} · ${o.projectId}</p></div><span class="tag">${statusNames[o.status]}</span></div><div class="actions"><a class="btn secondary small" href="#/order/${o.id}">Lihat pesanan</a>${o.status==='pending'?`<button class="btn secondary small" data-action="order-uncertain" data-order="${o.id}">Tandai belum pasti</button><button class="link-btn" data-action="order-failed" data-order="${o.id}">Catat gagal</button>`:''}${['uncertain','expired','failed'].includes(o.status)?`<button class="btn secondary small" data-action="order-reconcile" data-order="${o.id}">Rekonsiliasi uji</button>`:''}${o.status==='paid'?`<button class="btn secondary small" data-action="request-refund" data-order="${o.id}">Catat pengembalian</button>`:''}${o.status==='refund_pending'?`<button class="btn secondary small" data-action="finish-refund" data-order="${o.id}">Selesaikan pengembalian</button>`:''}</div>${o.refundReason?`<p class="op-meta">Alasan: ${esc(o.refundReason)} · Referensi: ${esc(o.refundReference||'menunggu')}</p>`:''}</article>`).join(''):'<div class="empty"><h3>Belum ada pesanan</h3><p>Pesanan uji akan muncul setelah pelanggan memilih resolusi tinggi.</p></div>'}`;
    if(tab==='support')content=`<h2>Antrean bantuan</h2>${state.tickets.length?state.tickets.slice(0,pageLimit).map(t=>`<article class="op-card"><div class="row"><h3>${esc(t.subject)}</h3><span class="tag">${statusNames[t.status]}</span></div><p class="full-detail">${esc(t.message)}</p><div class="op-meta">${t.id}${t.project?' · '+esc(t.project):''}${t.order?' · '+esc(t.order):''} · Izin lihat foto: ${t.imageConsent?'diberikan':'tidak'}</div>${t.reply?`<div class="notice">${esc(t.reply)}</div>`:''}<div class="actions"><button class="btn secondary small" data-action="reply" data-ticket="${t.id}">Balas permintaan</button>${t.imageConsent&&M.project(state,t.project)?`<button class="link-btn" data-action="support-image" data-ticket="${t.id}">Tinjau foto berizin</button>`:''}</div></article>`).join(''):'<div class="empty"><h3>Tidak ada permintaan</h3><p>Permintaan pelanggan ditautkan ke proyek dan pesanan, tanpa membuka foto secara otomatis.</p></div>'}`;
    if(tab==='settings')content=`<h2>Batas & ketersediaan</h2><form id="settings-form" class="op-card"><div class="settings-row od-row"><label for="admission" class="od-field od-fill">Terima pembuatan baru<small>Download lama tetap tersedia ketika dijeda.</small></label><input class="od-fixed" type="checkbox" id="admission" name="admission" ${state.controls.admission?'checked':''}></div><div class="settings-row od-row"><label for="outage" class="od-field od-fill">Gangguan layanan uji<small>Tahan proses; hindari permintaan ganda.</small></label><input class="od-fixed" type="checkbox" id="outage" name="outage" ${state.controls.outage?'checked':''}></div>${[['budget','Anggaran uji (Rp)',1000,1000000],['unitCost','Biaya contoh per proses (Rp)',0,100000],['concurrency','Proses bersamaan',1,5],['retries','Batas kegagalan teknis',1,5]].map(([k,label,min,max])=>`<div class="settings-row od-row"><label for="${k}" class="od-field od-fill">${label}</label><input class="input od-fixed" id="${k}" name="${k}" type="number" min="${min}" max="${max}" value="${state.controls[k]}" required></div>`).join('')}<p class="fine mt16">Semua biaya merupakan parameter simulasi. Tidak ada tagihan penyedia. Menghapus proyek tidak mengembalikan jatah akun.</p><div id="settings-error" class="field-error" role="alert"></div><button class="btn primary mt24" type="submit">Simpan pengaturan</button></form>`;
    return `<section class="wrap page"><div class="page-header"><div><div class="eyebrow">MomenRia · Ruang pengelola</div><h1>Di balik setiap momen.</h1><p>Operasi lokal untuk katalog, pesanan, dan bantuan.</p></div><a class="btn secondary" href="#/">Lihat katalog ${icon('arrow')}</a></div><div class="operator-layout"><nav class="operator-nav" aria-label="Navigasi pengelola">${links.map(([id,n,i])=>`<a href="#/operator/${id}" class="${tab===id?'active':''}">${icon(i)}${n}</a>`).join('')}</nav><div class="operator-main"><p class="notice mb16">Ruang contoh lokal. Akses pengelola ini belum menggunakan autentikasi produksi.</p>${content||'<p>Pilih menu pengelola.</p>'}</div></div></section>`;
  }
  function showModal(title,body,wide=false) {
    const dialog=$('#dialog');modalReturn=document.activeElement;
    dialog.className='dialog'+(wide?' wide':'');
    dialog.innerHTML=`<div class="dialog-head"><h2 id="dialog-title">${title}</h2><button class="icon-btn" data-action="close" aria-label="Tutup">${icon('close')}</button></div><div class="dialog-body">${body}</div>`;
    if(!dialog.open)dialog.showModal();
  }
  function closeModal() {
    uploadSerial+=1;uploadContext=null;
    if($('#dialog').open)$('#dialog').close();
    modalReturn?.focus?.({preventScroll:true});
  }
  function toast(text) {
    clearTimeout(toastTimer);$('#toast').textContent=text;$('#toast').hidden=false;
    toastTimer=setTimeout(()=>{$('#toast').hidden=true;},5000);
  }
  function confirmAction(title,text,action,attrs='',label='Lanjutkan',danger=false) {
    showModal(title,`<p>${text}</p><div class="dialog-actions"><button class="btn secondary" data-action="close">Batal</button><button class="btn ${danger?'danger':'primary'}" data-action="${action}" ${attrs}>${label}</button></div>`);
  }
  function account(next=null) {
    if(state.verified&&!next){showModal('Akun contohmu',`<p>Proyek dan pesanan tersimpan di browser ini. Tidak ada akun cloud, kata sandi, atau verifikasi identitas sungguhan.</p><div class="notice"><strong>Jatah pembuatan</strong>${state.creationsUsed?'Sudah digunakan':'1 pembuatan gratis tersedia'}</div><div class="dialog-actions"><a class="btn primary" href="#/projects">Buka foto saya</a></div>`);return;}
    showModal('Yuk, lanjut bikin foto',`<p>Masuk dulu sebelum tambah foto, ya. Jadi, draf dan pesanan bisa kamu buka lagi di browser ini.</p><div class="notice"><strong>Akun contoh, tanpa data pribadi</strong>Tidak ada OTP atau pesan yang dikirim. Verifikasi dan pemulihan lintas perangkat belum tersedia.</div><div class="dialog-actions"><button class="btn primary" data-action="verify" ${next?`data-project="${next.p.id}" data-slot="${next.slot}" data-mode="${next.mode}"`:''}>Gunakan akun contoh ${icon('arrow')}</button></div>`);
  }
  function faceActions(p,slot) {
    selectedFace=slot;render(true);
    const v=M.current(p),t=M.template(p.templateId),s=v?v.refs[slot]:p.sources.find(x=>x.id===p.assignments[slot]);
    M.log(state,'face_action_opened',{project:p.id,slot});persist();
    const comparison=v?`<div class="compare-grid"><figure>${s?.src?`<img src="${esc(s.src)}" alt="Referensi wajah ${slot+1}">`:'<div class="image-empty">Sumber kedaluwarsa</div>'}<figcaption>Foto referensi</figcaption></figure><figure><div class="comparison-face">${faceCrop(t,slot)}</div><figcaption>Wajah pada contoh hasil</figcaption></figure></div><p class="fine">Wajah di hasil ini masih contoh buatan AI, ya. Belum memakai wajah dari fotomu.</p>`:`<p>Tambahkan foto di posisi ini. Posisinya disimpan dulu, fotonya belum dibuat.</p>`;
    showModal(`Wajah ${slot+1}`,`${comparison}<div class="od-stack mt24"><button class="btn primary" data-action="open-picker" data-project="${p.id}" data-slot="${slot}" data-mode="${v?'correction':'draft'}">${icon('upload')}Ganti wajah</button><button class="btn secondary" data-action="enhance" data-project="${p.id}" data-slot="${slot}" ${!v||p.correctionUsed||M.activeJob(p)?'disabled':''}>${icon('spark')}Tingkatkan kualitas</button><p class="fine">${!v?'Tersedia setelah foto dibuat':p.correctionUsed?'Jatah koreksi bersama sudah digunakan.':'Perbaikan untuk orang yang sama; memakai 1 koreksi bersama.'}</p>${v?`<div class="field"><label for="face-feedback">Penilaian wajah ini</label><select id="face-feedback" class="input" data-project="${p.id}" data-slot="${slot}"><option value="">Belum dinilai</option>${[['accepted','Sudah sesuai'],['likeness','Belum mirip'],['wrong','Orang tidak sesuai'],['blur','Kurang jelas'],['missing','Wajah hilang / ganda']].map(([k,n])=>`<option value="${k}" ${v.feedback[slot]===k?'selected':''}>${n}</option>`).join('')}</select></div>`:`<button class="link-btn" data-action="undo-draft" data-project="${p.id}" ${p.undo.length?'':'disabled'}>${icon('undo')}Urungkan penempatan</button>`}</div>`);
  }
  function picker(p,slot,mode='draft') {
    if(!state.verified){account({p,slot,mode});return;}
    if(M.activeJob(p))throw Error('Tunggu proses selesai sebelum mengganti referensi.');
    if(mode==='correction'&&p.correctionUsed)throw Error('Jatah koreksi sudah digunakan. Hasil sebelumnya tetap bisa didownload.');
    uploadContext={project:p.id,slot,mode,source:null};
    showModal(mode==='correction'?'Referensi yang lebih baik':'Foto untuk wajah '+(slot+1),`<p>${mode==='correction'?'Pilih foto lain dari orang yang sama, ya. Mengganti orangnya belum bisa.':'Pilih satu foto terang, menghadap depan, tanpa wajah lain atau penghalang.'}</p><div class="notice"><strong>Hanya di browser ini</strong>Foto tidak dikirim ke penyedia AI. Sumber berlaku sampai ${date(Date.now()+7*M.DAY)}; hasil contoh berlaku 30 hari setelah selesai.</div><label class="check"><input type="checkbox" id="photo-consent"><span>Aku punya hak untuk memakai foto ini dan izin dari orang di dalamnya, termasuk izin wali yang berwenang untuk foto anak.</span></label><div id="picker-controls" hidden><div class="upload-zone">${icon('upload')}<strong>Pilih foto dari perangkat</strong><span>JPEG atau PNG · Maksimal 10 MB · Satu wajah</span><input type="file" id="photo-file" accept="image/jpeg,image/png" aria-label="Pilih foto wajah"></div><p id="upload-status" class="small-copy mt16" role="status"></p><div id="upload-error" class="field-error" role="alert"></div><div id="upload-review"></div><p class="small-copy mt24"><strong>Atau gunakan foto contoh</strong></p><div class="sample-grid">${M.template(p.templateId).faces.map((_,i)=>`<button class="sample-choice" data-action="sample-source" data-slot="${i}">${faceCrop(M.template(p.templateId),i)}<span>Contoh ${i+1}</span></button>`).join('')}</div>${p.sources.some(s=>s.src&&s.expiresAt>Date.now())?`<p class="small-copy">Foto di proyek ini</p><div class="source-reuse mt16">${p.sources.filter(s=>s.src&&s.expiresAt>Date.now()).map(s=>`<button data-action="reuse-source" data-source="${s.id}"><img src="${esc(s.src)}" alt="${esc(s.name)}" width="64" height="64"><span class="od-truncate">${esc(s.name)}</span></button>`).join('')}</div>`:''}</div><p class="fine mt16">Izin ini nggak termasuk publikasi, pemasaran, atau pelatihan model. Di demo ini, jumlah dan kualitas wajah belum dicek otomatis.</p>`);
  }
  function portraitAssets() {
    if(window.PortraitAssets)return Promise.resolve(window.PortraitAssets);
    if(!portraitBundle)portraitBundle=new Promise((resolve,reject)=>{
      const script=document.createElement('script');
      script.src='assets/portraits.js';
      script.onload=()=>{script.remove();window.PortraitAssets?resolve(window.PortraitAssets):reject(Error('Gambar contoh belum tersedia. Coba lagi, ya.'));};
      script.onerror=()=>{script.remove();reject(Error('Gambar contoh gagal dimuat. Coba lagi, ya.'));};
      document.head.appendChild(script);
    }).catch(error=>{portraitBundle=null;throw error;});
    return portraitBundle;
  }
  function imageFor(id) {
    if(!imagePromises.has(id))imagePromises.set(id,portraitAssets().then(assets=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('Gambar contoh nggak bisa dibaca. Coba lagi, ya.'));img.src=assets[id];})).catch(error=>{imagePromises.delete(id);throw error;}));
    return imagePromises.get(id);
  }
  async function sampleSource(p,slot) {
    const t=M.template(p.templateId),img=await imageFor(t.id),[x,y]=t.faces[slot];
    const c=document.createElement('canvas');c.width=320;c.height=320;
    c.getContext('2d').drawImage(img,x*1448-145,y*1086-145,290,290,0,0,320,320);
    return {id:'sample-'+t.id+'-'+slot,name:'Contoh wajah '+(slot+1),src:c.toDataURL('image/jpeg',.92),consentAt:Date.now(),consentVersion:'local-v1',expiresAt:Date.now()+7*M.DAY,sample:true};
  }
  async function readUpload(file) {
    if(!uploadContext||!$('#photo-consent')?.checked)return;
    const serial=++uploadSerial;$('#upload-error').textContent='';$('#upload-review').innerHTML='';
    if(!file||!['image/jpeg','image/png'].includes(file.type))throw Error('Format belum didukung. Ekspor foto sebagai JPEG atau PNG, lalu pilih lagi.');
    if(file.size>10*1024*1024)throw Error('Foto melebihi 10 MB. Pilih foto yang lebih kecil.');
    $('#upload-status').innerHTML=`Membaca foto di perangkat… <button class="link-btn" data-action="cancel-upload">Batalkan</button>`;
    const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('Foto nggak bisa dibaca. Pilih kembali file dari perangkat.'));r.readAsDataURL(file);});
    const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('File gambar rusak atau tidak terbaca. Pilih JPEG atau PNG lain.'));img.src=data;});
    if(serial!==uploadSerial||!uploadContext)return;
    if(image.naturalWidth<96||image.naturalHeight<96)throw Error('Foto terlalu kecil. Pilih foto yang lebih jelas, minimal 96 px di setiap sisi.');
    const scale=Math.min(1,1280/Math.max(image.naturalWidth,image.naturalHeight)),c=document.createElement('canvas');c.width=Math.round(image.naturalWidth*scale);c.height=Math.round(image.naturalHeight*scale);c.getContext('2d').drawImage(image,0,0,c.width,c.height);
    const src=c.toDataURL('image/jpeg',.86),buffer=await file.arrayBuffer();
    let key=file.name+'-'+file.size+'-'+file.lastModified;
    if(window.crypto?.subtle)key=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer))).map(x=>x.toString(16).padStart(2,'0')).join('');
    if(serial!==uploadSerial||!uploadContext)return;
    uploadContext.source={id:'photo-'+key,name:file.name,src,consentAt:Date.now(),consentVersion:'local-v1',expiresAt:Date.now()+7*M.DAY,sample:false};
    $('#upload-status').textContent='Foto terbaca. Konfirmasi wajah sebelum dipakai.';
    $('#upload-review').innerHTML=`<img class="upload-preview" src="${src}" alt="Preview foto yang dipilih"><p class="small-copy full-detail">${esc(file.name)}</p><label class="check"><input type="checkbox" id="one-face"><span>Hanya satu wajah terlihat jelas, dan foto ini untuk ${uploadContext.mode==='correction'?'orang yang sama':'posisi yang dipilih'}.</span></label><button class="btn primary block" data-action="use-upload">Pakai foto ini</button>`;
  }
  function useSource(source,move=false) {
    const ctx=uploadContext;if(!ctx)throw Error('Buka kembali pemilih foto.');
    const p=M.project(state,ctx.project);if(!p)throw Error('Proyek tidak tersedia.');
    if(ctx.mode==='correction') {
      const old=M.current(p).refs[ctx.slot];
      p.renewedRefs=p.renewedRefs||{};p.renewedRefs[old.id]=source;
      const existing=p.sources.find(s=>s.id===source.id);if(existing)Object.assign(existing,source);else p.sources.push(source);
      persist();closeModal();render(true);
      const issue=M.admissionIssue(state,p,'correction');
      if(issue){toast('Referensi diperbarui. '+issue);return;}
      confirmAction('Koreksi wajah '+(ctx.slot+1)+'?', 'Pakai foto orang yang sama, ya. Ini memakai satu kali koreksi untuk proyekmu. Hasil sebelumnya tetap ada. Karena masih simulasi, wajah di contoh AI nggak benar-benar diganti.', 'confirm-correction',`data-project="${p.id}" data-slot="${ctx.slot}"`,'Mulai koreksi');return;
    }
    const other=M.assign(state,p,ctx.slot,source,move);
    if(other>=0){uploadContext.source=source;showModal('Foto sudah digunakan',`<p>Foto ini berada di wajah ${other+1}. Pindahkan ke wajah ${ctx.slot+1}? Posisi sebelumnya akan kosong.</p><div class="dialog-actions"><button class="btn secondary" data-action="back-picker">Pilih foto lain</button><button class="btn primary" data-action="move-source">Pindahkan foto</button></div>`);return;}
    persist();closeModal();render(true);toast('Foto untuk wajah '+(ctx.slot+1)+' tersimpan.');
  }
  async function resultData(p,v,free=true) {
    const key=v.id+':'+free;if(sampleResults.has(key))return sampleResults.get(key);
    const img=await imageFor(v.templateId),master=document.createElement('canvas');master.width=2048;master.height=1536;
    const ctx=master.getContext('2d');ctx.drawImage(img,0,0,2048,1536);
    if(v.greeting){ctx.fillStyle='rgba(255,255,255,.94)';ctx.fillRect(0,1376,2048,160);ctx.fillStyle='#234b39';ctx.textAlign='center';ctx.font='52px Georgia';ctx.fillText(v.greeting,1024,1468,1856);}
    ctx.textAlign='left';ctx.font='20px sans-serif';ctx.fillStyle='#ffffff';ctx.fillRect(48,48,152,40);ctx.fillStyle='#234b39';ctx.fillText('ILUSTRASI AI',60,76);
    let output=master;
    if(free){output=document.createElement('canvas');output.width=768;output.height=576;const c=output.getContext('2d');c.drawImage(master,0,0,768,576);c.fillStyle='rgba(24,37,30,.78)';c.fillRect(540,520,204,40);c.fillStyle='white';c.font='20px Georgia';c.textAlign='center';c.fillText('MomenRia · contoh',642,546);}
    const data=output.toDataURL('image/png');sampleResults.set(key,data);return data;
  }
  async function populatePreviews() {
    for(const img of document.querySelectorAll('[data-preview]')) {
      const [pid,vid]=img.dataset.preview.split(':'),p=M.project(state,pid),v=p?.versions.find(v=>v.id===vid);if(!v)continue;
      try{const src=await resultData(p,v);if(img.isConnected&&M.project(state,pid))img.src=src;}catch(e){toast(e.message);}
    }
  }
  async function download(p,v,free) {
    if(!p||p.deleted||!v||v.expiresAt<=Date.now())throw Error('Hasil tidak tersedia atau sudah kedaluwarsa. Hubungi bantuan.');
    if(!free&&!M.entitlement(state,p,v))throw Error('Versi ini belum dibeli. Selesaikan pembayaran uji untuk membuka download.');
    toast('Menyiapkan file contoh…');const src=await resultData(p,v,free);
    if(p.deleted||(!free&&!M.entitlement(state,p,v)))throw Error('Akses file berubah. Buka kembali pesanan.');
    const a=document.createElement('a');a.href=src;a.download=`MomenRia-${p.id}-v${v.number}-${free?'preview':'contoh-HD'}.png`;document.body.append(a);a.click();a.remove();
    M.log(state,'download_completed',{project:p.id,version:v.id,kind:free?'preview':'sample-master'});persist();toast('File contoh sudah siap. Cek folder Download di browsermu, ya.');
  }
  function supportForm(pid='',oid='') {
    showModal('Bantuan untuk momenmu',`<p>Ceritakan kendalanya. Permintaan ini disimpan lokal, tidak dikirim ke tim sungguhan.</p><form id="support-form" data-project="${esc(pid)}" data-order="${esc(oid)}"><div class="field"><label for="support-subject">Topik <span class="required">*</span></label><select id="support-subject" name="subject" class="input"><option>Pembuatan foto</option><option>Wajah belum sesuai</option><option>Pembayaran atau download</option><option>Pengembalian dana</option><option>Privasi dan penghapusan</option></select></div><div class="field"><label for="support-message">Ceritakan kendala <span class="required">*</span></label><textarea id="support-message" name="message" class="input" minlength="10" maxlength="1000" required></textarea><span class="help">10–1.000 karakter. Jangan sertakan kata sandi atau data pembayaran.</span><span id="support-error" class="field-error" role="alert"></span></div>${pid?`<p class="fine">Proyek ${esc(pid)}${oid?' · Pesanan '+esc(oid):''}</p><label class="check"><input type="checkbox" name="imageConsent"><span>Saya mengizinkan pengelola contoh melihat foto proyek ini untuk bantuan.</span></label>`:''}<div class="dialog-actions"><button type="submit" class="btn primary">Simpan permintaan ${icon('arrow')}</button></div></form>`);
  }
  function regionsForm(t) {
    const c=state.catalog[t.id],faces=c.faces||t.faces;
    showModal('Wilayah wajah · '+t.name,`<p>Titik pusat dinyatakan sebagai persentase gambar. Perubahan hanya digunakan oleh proyek baru.</p><div class="portrait-canvas" id="region-preview">${photo(t)}${faces.map(([x,y],i)=>`<span class="face-target" id="region-${i}" style="--x:${x*100}%;--y:${y*100}%"><span class="number">${i+1}</span></span>`).join('')}</div><form id="regions-form" data-template="${t.id}" class="mt24">${faces.map(([x,y],i)=>`<div class="op-grid"><div class="field"><label for="face-x-${i}">Wajah ${i+1} · X (%)</label><input class="input" id="face-x-${i}" name="x${i}" type="number" min="8" max="92" step="0.1" value="${(x*100).toFixed(1)}" required></div><div class="field"><label for="face-y-${i}">Wajah ${i+1} · Y (%)</label><input class="input" id="face-y-${i}" name="y${i}" type="number" min="12" max="88" step="0.1" value="${(y*100).toFixed(1)}" required></div></div>`).join('')}<label class="check"><input type="checkbox" name="confirmed" required><span>Saya telah meninjau setiap target pada gambar contoh.</span></label><div class="field-error" id="regions-error" role="alert"></div><button type="submit" class="btn primary">Simpan versi wilayah</button></form>`,true);
  }
  async function handleAction(el) {
    const a=el.dataset.action,p=M.project(state,el.dataset.project),slot=Number(el.dataset.slot||0),o=state.orders.find(x=>x.id===el.dataset.order),t=M.templates.find(x=>x.id===el.dataset.template);
    if(a==='close')return closeModal();
    if(a==='menu')return showModal('Navigasi',`<nav class="modal-nav"><a href="#/">Studio</a><a href="#/projects">Foto saya</a><a href="#/orders">Pesanan</a><a href="#/support">Bantuan</a><a href="#/privacy">Privasi</a><a href="#/operator">Pengelola</a></nav>`);
    if(a==='studio-face')return openStudioFace(p,slot);
    if(a==='studio-template'&&t){if(p&&p.templateId!==t.id)return confirmAction('Ganti ke '+t.name+'?', 'Penempatan wajah dikosongkan. Foto asli tetap tersedia untuk dipasangkan lagi.', 'replace-template',`data-project="${p.id}" data-template="${t.id}"`,'Ganti template');if(!p){studioTemplateId=t.id;selectedFace=0;return render(true);}return;}
    if(a==='new-studio'){const draft=M.createProject(state,studioTemplate(p).id);persist();return go('/editor/'+draft.id);}
    if(a==='template-preview'&&t)return showModal(t.name,`${photo(t)}<p class="mt16">Contoh AI · ${t.people} orang · ${t.attire}</p>`,true);
    if(a==='account')return account();
    if(a==='verify'){state.verified=true;M.log(state,'account_verified_demo');persist();closeModal();render(true);return p?picker(p,slot,el.dataset.mode):toast('Akun contoh siap.');}
    if(a==='filter'){occasion=el.dataset.value;return render(true);}
    if(a==='clear-filters'){occasion='Semua';count='all';return render(true);}
    if(a==='face'&&p)return faceActions(p,slot);
    if(a==='open-picker'&&p)return picker(p,slot,el.dataset.mode);
    if(a==='back-picker'&&uploadContext){const c={...uploadContext};return picker(M.project(state,c.project),c.slot,c.mode);}
    if(a==='sample-source'&&uploadContext){const ctx=uploadContext,label=el.textContent;el.disabled=true;el.textContent='Menyiapkan contoh…';try{const source=await sampleSource(M.project(state,ctx.project),slot);if(uploadContext!==ctx)return;return useSource(source);}finally{el.disabled=false;el.textContent=label;}}
    if(a==='reuse-source'&&uploadContext){const owner=M.project(state,uploadContext.project);return useSource(owner.sources.find(s=>s.id===el.dataset.source));}
    if(a==='move-source'&&uploadContext)return useSource(uploadContext.source,true);
    if(a==='use-upload'){if(!$('#one-face')?.checked)throw Error('Konfirmasi bahwa hanya satu wajah terlihat jelas sebelum melanjutkan.');return useSource(uploadContext.source);}
    if(a==='cancel-upload'){uploadSerial++;if(uploadContext)uploadContext.source=null;$('#upload-status').textContent='Pembacaan dibatalkan. Foto lama tidak berubah.';$('#upload-review').innerHTML='';$('#photo-file').value='';return;}
    if(a==='undo-draft'&&p){M.undoAssignment(p);persist();closeModal();render(true);return toast('Penempatan sebelumnya dipulihkan.');}
    if(a==='generate'&&p){M.startJob(state,p);persist();closeModal();return render(true);}
    if(a==='check-job'&&p){M.tick(state);persist();render(true);return toast(statusNames[p.job.status]);}
    if(a==='retry-job'&&p){const type=p.job.type,face=p.job.slot;M.startJob(state,p,type,face);persist();return render(true);}
    if(a==='previous-result'&&p){$('#main').innerHTML=resultView(p,true);populatePreviews();return;}
    if(a==='enhance'&&p){const issue=M.admissionIssue(state,p,'correction');if(issue)throw Error(issue);return confirmAction('Tingkatkan wajah '+(slot+1)+'?', 'Perbaiki wajah orang yang sama dengan satu kali koreksi untuk proyek ini. Karena masih demo, versi baru tetap pakai gambar contoh. Wajahnya belum diproses AI.', 'confirm-correction',`data-project="${p.id}" data-slot="${slot}"`,'Mulai koreksi');}
    if(a==='confirm-correction'&&p){M.startJob(state,p,'correction',slot);persist();closeModal();return render(true);}
    if(a==='change-template'&&p){if(p.versions.length)throw Error('Variasi template setelah pembuatan belum tersedia.');return showModal('Pilih suasana baru',`<p>Penempatan wajah saat ini akan dikosongkan setelah konfirmasi. Foto asli tetap tersedia di proyek.</p><div class="od-stack">${M.templates.filter(x=>x.id!==p.templateId).map(x=>`<button class="face-row" data-action="choose-replacement" data-project="${p.id}" data-template="${x.id}"><span class="od-field od-fill"><b>${x.name}</b><small>${x.people} orang · ${x.attire}</small></span>${icon('arrow')}</button>`).join('')}</div>`);}
    if(a==='choose-replacement'&&p&&t)return confirmAction('Ganti ke '+t.name+'?', 'Penempatan wajah dikosongkan. Foto yang sudah kamu tambahkan tetap tersedia untuk dipasangkan lagi.', 'replace-template',`data-project="${p.id}" data-template="${t.id}"`,'Ganti template');
    if(a==='replace-template'&&p&&t){M.changeTemplate(state,p,t.id);selectedFace=0;persist();closeModal();return render(true);}
    if(a==='greeting'&&p){const v=M.current(p);return showModal('Ucapan kecil, makna besar',`<p>Tambahkan ucapan di fotomu, yuk. Ucapan disimpan sebagai versi baru. Pesanan dan foto yang sudah dibeli tetap sama.</p><form id="greeting-form" data-project="${p.id}"><div class="field"><label for="greeting">Ucapan (opsional)</label><input id="greeting" name="greeting" class="input" maxlength="48" value="${esc(v.greeting)}" placeholder="Selalu dekat, di mana pun berada"><span class="help">Maksimal 48 karakter, satu baris.</span><span id="greeting-error" class="field-error" role="alert"></span></div><button type="submit" class="btn primary">Simpan versi ucapan</button></form>`);}
    if(a==='zoom'&&p){const v=M.current(p);showModal('Versi '+v.number+' · Lihat seluruh foto',`<img class="od-media" data-preview="${p.id}:${v.id}" src="${M.template(p.templateId).image}" width="768" height="576" alt="Preview versi ${v.number}"><p class="fine mt16">Contoh AI. Untuk membandingkan, tutup tampilan ini dan pilih wajah.</p>`,true);return populatePreviews();}
    if(a==='checkout'&&p){const v=M.current(p);showModal('Ini foto pilihanmu?',`<img class="od-media" data-preview="${p.id}:${v.id}" src="${M.template(p.templateId).image}" width="768" height="576" alt="Versi yang akan dibeli"><div class="order-rows"><div class="order-row"><span>Versi pilihan</span><b>Versi ${v.number}</b></div><div class="order-row"><span>Harga uji</span><b>Rp19.900</b></div><div class="order-row"><span>Tersedia sampai</span><b>${date(v.expiresAt)}</b></div></div><p>Foto contoh 2048 × 1536 px. Pembayaran uji tidak mengubah wajah atau membuat gambar baru.</p><div class="dialog-actions"><button class="btn secondary" data-action="close">Cek lagi</button><button class="btn primary" data-action="confirm-checkout" data-project="${p.id}" data-version="${v.id}">Lanjut ke pembayaran</button></div>`);return populatePreviews();}
    if(a==='confirm-checkout'&&p){if(p.currentVersion!==el.dataset.version)throw Error('Versi pilihan berubah. Tinjau kembali sebelum membeli.');const order=M.order(state,p);persist();closeModal();return go('/order/'+order.id);}
    if(a==='pay'&&o){el.disabled=true;el.textContent='Memverifikasi pembayaran uji…';await new Promise(r=>setTimeout(r,450));M.pay(state,o);persist();return render(true);}
    if(a==='check-payment'&&o){M.tick(state);persist();render(true);return toast(statusNames[o.status]+'. Tidak ada tagihan nyata.');}
    if(a==='reorder'&&o){const owner=M.project(state,o.projectId);if(!owner)throw Error('Proyek sudah dihapus.');owner.currentVersion=o.versionId;const next=M.order(state,owner);persist();return go('/order/'+next.id);}
    if(a==='download-free'&&p)return download(p,M.current(p),true);
    if(a==='download-paid'&&p)return download(p,M.current(p),false);
    if(a==='download-order'&&o){const owner=M.project(state,o.projectId);return download(owner,owner?.versions.find(v=>v.id===o.versionId),false);}
    if(a==='support')return supportForm(el.dataset.project||'',el.dataset.order||'');
    if(a==='delete'&&p)return confirmAction('Hapus proyek ini?', 'Semua foto asli, hasil, dan akses download proyek ini akan dihapus dari browser. Proses berjalan dihentikan. Pesanan uji yang lunas masuk antrean pengembalian. Tindakan ini nggak bisa dibatalkan.', 'confirm-delete',`data-project="${p.id}"`,'Hapus proyek',true);
    if(a==='confirm-delete'&&p){M.removeProject(state,p);sampleResults.clear();persist();closeModal();go('/projects');return toast('Foto proyek dihapus. Catatan pesanan uji dipertahankan.');}
    if(a==='load-more'){pageLimit+=24;return render(true);}
    if(a==='toggle-template'&&t){const c=state.catalog[t.id];if(!c.published&&(!c.regions||!c.evidence))throw Error('Lengkapi wilayah dan tanda evaluasi contoh sebelum publikasi.');c.published=!c.published;M.log(state,c.published?'template_published':'template_paused',{template:t.id,version:c.version});persist();return render(true);}
    if(a==='regions'&&t)return regionsForm(t);
    if(a==='evidence'&&t){const c=state.catalog[t.id];c.evidence=!c.evidence;if(!c.evidence)c.published=false;M.log(state,'sample_evidence_changed',{template:t.id});persist();return render(true);}
    if(a==='fail-job'&&p){M.failJob(state,p);persist();return render(true);}
    if(a==='allow-retry'&&p){p.failures=0;M.log(state,'retry_exception',{project:p.id});persist();render(true);return toast('Percobaan ulang diizinkan; jatah yang sudah dipakai tidak berubah.');}
    if(a==='order-uncertain'&&o&&o.status==='pending'){o.status='uncertain';M.log(state,'payment_uncertain',{order:o.id});persist();return render(true);}
    if(a==='order-failed'&&o&&o.status==='pending'){o.status='failed';M.log(state,'payment_failed',{order:o.id});persist();return render(true);}
    if(a==='order-reconcile'&&o&&['uncertain','expired','failed'].includes(o.status)){const owner=M.project(state,o.projectId),v=owner?.versions.find(v=>v.id===o.versionId);if(v&&v.expiresAt>Date.now()){o.status='paid';o.paidAt=Date.now();M.log(state,'payment_verified',{order:o.id,project:owner.id,version:v.id,source:'reconciliation-demo'});}else{o.status='refund_pending';M.log(state,'refund_requested',{order:o.id});}persist();render(true);return toast('Pembayaran terlambat uji direkonsiliasi untuk versi yang sama.');}
    if(a==='request-refund'&&o)return showModal('Catat pengembalian uji',`<p>Pesanan ${o.id} · ${money(o.amount)}. Tidak ada dana sungguhan yang dipindahkan.</p><form id="refund-form" data-order="${o.id}"><div class="field"><label for="refund-reason">Alasan <span class="required">*</span></label><textarea class="input" id="refund-reason" name="reason" minlength="10" maxlength="500" required></textarea></div><button class="btn primary" type="submit">Catat permintaan</button></form>`);
    if(a==='finish-refund'&&o&&o.status==='refund_pending'){o.status='refunded';o.refundReference=M.uid('UJI-REF');o.refundAmount=o.amount;o.refundedAt=Date.now();M.log(state,'refund_recorded',{order:o.id});persist();return render(true);}
    if(a==='reply'){const ticket=state.tickets.find(t=>t.id===el.dataset.ticket);if(!ticket)return;return showModal('Balas permintaan',`<p>${esc(ticket.subject)} · ${ticket.id}</p><form id="reply-form" data-ticket="${ticket.id}"><div class="field"><label for="reply-message">Balasan <span class="required">*</span></label><textarea class="input" id="reply-message" name="reply" minlength="5" maxlength="1000" required>${esc(ticket.reply||'')}</textarea></div><div class="field"><label for="reply-status">Status</label><select class="input" id="reply-status" name="status">${['waiting','action_required','resolved'].map(s=>`<option value="${s}" ${ticket.status===s?'selected':''}>${statusNames[s]}</option>`).join('')}</select></div><button class="btn primary" type="submit">Simpan balasan</button></form>`);}
    if(a==='support-image'){const ticket=state.tickets.find(t=>t.id===el.dataset.ticket),owner=M.project(state,ticket?.project);if(!ticket?.imageConsent||!owner)throw Error('Tidak ada izin atau proyek tidak tersedia.');M.log(state,'support_image_access',{project:owner.id,ticket:ticket.id,actor:'operator-demo',reason:ticket.subject});persist();const v=M.current(owner);showModal('Foto proyek berizin',`${v?`<img class="od-media" data-preview="${owner.id}:${v.id}" src="${M.template(owner.templateId).image}" width="768" height="576" alt="Hasil contoh proyek berizin">`:'<p>Belum ada hasil.</p>'}<div class="compare-grid">${owner.sources.filter(s=>s.src).map(s=>`<img class="od-media" src="${esc(s.src)}" alt="Referensi berizin ${esc(s.name)}">`).join('')}</div><p class="fine">Akses ini dicatat dengan alasan bantuan.</p>`,true);return populatePreviews();}
  }
  async function handleSubmit(form) {
    const data=new FormData(form),p=M.project(state,form.dataset.project);
    if(form.id==='greeting-form'&&p){M.greeting(state,p,String(data.get('greeting')));persist();closeModal();render(true);return toast('Ucapan disimpan dalam versi baru.');}
    if(form.id==='support-form'){const text=String(data.get('message')).trim();if(text.length<10)throw Error('Ceritakan kendala minimal 10 karakter.');const ticket={id:M.uid('HELP'),at:Date.now(),subject:String(data.get('subject')),message:text,project:form.dataset.project,order:form.dataset.order,imageConsent:data.has('imageConsent'),status:'waiting'};state.tickets.unshift(ticket);M.log(state,'support_requested',{project:ticket.project,ticket:ticket.id});persist();closeModal();go('/support');return toast('Permintaan contoh tersimpan.');}
    if(form.id==='settings-form'){const next={admission:data.has('admission'),outage:data.has('outage')};for(const [key,min,max]of [['budget',1000,1000000],['unitCost',0,100000],['concurrency',1,5],['retries',1,5]]){const n=Number(data.get(key));if(!Number.isInteger(n)||n<min||n>max)throw Error('Nilai pengaturan berada di luar batas.');next[key]=n;}state.controls=next;M.log(state,'controls_updated');M.tick(state);persist();render(true);return toast('Pengaturan disimpan.');}
    if(form.id==='regions-form'){const t=M.template(form.dataset.template),c=state.catalog[t.id],faces=t.faces.map((_,i)=>[Number(data.get('x'+i))/100,Number(data.get('y'+i))/100]);if(faces.some(([x,y])=>!Number.isFinite(x)||!Number.isFinite(y)||x<.08||x>.92||y<.12||y>.88))throw Error('Titik wajah harus berada di dalam gambar.');if(faces.some(([x,y],i)=>faces.some(([xx,yy],j)=>i!==j&&Math.abs(x-xx)<.06&&Math.abs(y-yy)<.08)))throw Error('Dua target terlalu dekat. Pisahkan posisi sebelum menyimpan.');c.faces=faces;c.regions=true;c.version+=1;c.evidence=false;c.published=false;M.log(state,'template_regions_changed',{template:t.id,version:c.version});persist();closeModal();render(true);return toast('Versi baru disimpan sebagai draf. Tinjau tanda evaluasi sebelum terbit.');}
    if(form.id==='refund-form'){const o=state.orders.find(o=>o.id===form.dataset.order);if(!o||o.status!=='paid')throw Error('Pesanan nggak bisa dikembalikan pada status ini.');const reason=String(data.get('reason')).trim();if(reason.length<10)throw Error('Tuliskan alasan minimal 10 karakter.');o.status='refund_pending';o.refundReason=reason;M.log(state,'refund_requested',{order:o.id});persist();closeModal();return render(true);}
    if(form.id==='reply-form'){const t=state.tickets.find(t=>t.id===form.dataset.ticket);if(!t)return;const reply=String(data.get('reply')).trim();if(reply.length<5)throw Error('Tulis balasan minimal 5 karakter.');t.reply=reply;t.status=String(data.get('status'));t.repliedAt=Date.now();M.log(state,'support_replied',{ticket:t.id});persist();closeModal();return render(true);}
  }
  function go(path) {
    if(route()===path)render();else location.hash=path;
  }
  function render(keep=false) {
    let r=route(),html='';const main=$('#main'),currentScroll=main.scrollTop;
    if(lastRoute&&lastRoute!==r)scrollPositions[lastRoute]=currentScroll;
    const parts=r.split('/').filter(Boolean);
    try {
      if(parts[0]==='new') {const p=M.createProject(state,parts[1]);persist();history.replaceState(null,'','#/editor/'+p.id);r=route();parts.splice(0,parts.length,'editor',p.id);selectedFace=0;}
      if(!parts.length||parts[0]==='templates')html=homeView();
      else if(['how','pricing'].includes(parts[0]))html=guideView(parts[0]==='pricing');
      else if(parts[0]==='editor'){const p=M.project(state,parts[1]);html=p?editorView(p):`<section class="wrap page"><div class="empty"><h2>Proyek tidak tersedia</h2><p>Proyek mungkin sudah dihapus atau tersimpan di browser lain.</p><a class="btn secondary" href="#/projects">Kembali ke foto saya</a></div></section>`;}
      else if(parts[0]==='projects')html=projectsView();
      else if(parts[0]==='orders')html=projectsView(true);
      else if(parts[0]==='order'){const o=state.orders.find(o=>o.id===parts[1]);html=o?orderView(o):`<section class="wrap page"><div class="empty"><h2>Pesanan tidak ditemukan</h2><a class="btn secondary" href="#/orders">Semua pesanan</a></div></section>`;}
      else if(parts[0]==='privacy')html=privacyView();
      else if(parts[0]==='support')html=supportView();
      else if(parts[0]==='operator')html=operatorView(parts[1]||'overview');
      else html=`<section class="wrap page"><div class="empty"><h2>Halaman tidak tersedia</h2><a class="btn secondary" href="#/">Kembali ke beranda</a></div></section>`;
    }catch(e){html=`<section class="wrap page"><div class="empty"><h2>Momen ini belum tersedia</h2><p>${esc(e.message)}</p><a class="btn secondary" href="#/templates">Pilih template lain</a></div></section>`;}
    $('#header').innerHTML=header();$('#app-nav').innerHTML=appNavigation();main.innerHTML=html;
    document.title=(parts[0]==='operator'?'Pengelola · ':parts[0]==='editor'?'Studio · ':'')+'MomenRia — Studio foto keluarga';
    populatePreviews();
    requestAnimationFrame(()=>{main.scrollTop=keep?currentScroll:scrollPositions[r]||0;if(!keep)main.focus({preventScroll:true});});
    lastRoute=r;
  }
  function storageWarning() {
    memoryOnly=true;$('#storage-warning').hidden=false;$('#storage-warning').textContent='Browser belum bisa menyimpan perubahanmu. Kalau halaman ditutup, perubahannya hilang. Download foto yang mau kamu simpan dulu, ya.';
  }
  async function persist() {
    if(!db){storageWarning();return;}
    try{await new Promise((resolve,reject)=>{const tx=db.transaction('state','readwrite');tx.objectStore('state').put(state,'current');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}catch(e){storageWarning();}
  }
  function restoreStorage() {
    return new Promise((resolve,reject)=>{
      let connection=null,settled=false;
      const timer=setTimeout(()=>finish(Error('Storage timeout')),2000);
      function finish(error,saved) {
        if(settled)return;
        settled=true;clearTimeout(timer);
        if(error){connection?.close();reject(error);}
        else{db=connection;resolve(saved);}
      }
      try {
        const request=indexedDB.open('momenria-prototype',1);
        request.onupgradeneeded=()=>{if(settled)request.transaction.abort();else request.result.createObjectStore('state');};
        request.onerror=()=>finish(request.error||Error('Storage unavailable'));
        request.onblocked=()=>finish(Error('Storage blocked'));
        request.onsuccess=()=>{
          connection=request.result;
          if(settled){connection.close();return;}
          try {
            const tx=connection.transaction('state','readonly');
            const read=tx.objectStore('state').get('current');
            read.onsuccess=()=>finish(null,read.result);
            read.onerror=()=>finish(read.error||Error('Storage read failed'));
            tx.onabort=()=>finish(tx.error||Error('Storage read aborted'));
          }catch(error){finish(error);}
        };
      }catch(error){finish(error);}
    });
  }
  async function init() {
    try {
      const saved=await restoreStorage();
      if(saved?.schema===1)state=saved;
      if(M.tick(state))persist();
    }catch(e){storageWarning();}
    render();
    setInterval(()=>{if(M.tick(state)){persist();if(!$('#dialog').open)render(true);}},800);
  }
  document.addEventListener('click',async e=>{
    const el=e.target.closest('[data-action]');if(!el||el.disabled)return;e.preventDefault();
    try{await handleAction(el);}catch(error){if($('#upload-error')&&uploadContext)$('#upload-error').textContent=error.message;else toast(error.message);el.disabled=false;}
  });
  document.addEventListener('submit',async e=>{
    e.preventDefault();const form=e.target;if(!form.reportValidity())return;
    try{await handleSubmit(form);}catch(error){const field=form.querySelector('[role="alert"]');if(field)field.textContent=error.message;else toast(error.message);}
  });
  document.addEventListener('change',async e=>{
    const el=e.target;
    try {
      if(/^face-[xy]-\d+$/.test(el.id)){const [,axis,i]=el.id.split('-');$('#region-'+i)?.style.setProperty('--'+axis,el.value+'%');}
      if(el.id==='count-filter'){count=el.value;render(true);}
      if(el.id==='photo-consent')$('#picker-controls').hidden=!el.checked;
      if(el.id==='photo-file')await readUpload(el.files[0]);
      if(el.id==='version'){const p=M.project(state,el.dataset.project);if(p.versions.some(v=>v.id===el.value)){p.currentVersion=el.value;selectedFace=0;persist();render(true);}}
      if(el.id==='accept-faces'){const p=M.project(state,el.dataset.project);M.current(p).accepted=el.checked;M.log(state,'likeness_feedback',{project:p.id,version:p.currentVersion,accepted:el.checked});persist();}
      if(el.id==='face-feedback'){const p=M.project(state,el.dataset.project);M.current(p).feedback[el.dataset.slot]=el.value;M.log(state,'likeness_feedback',{project:p.id,version:p.currentVersion,slot:Number(el.dataset.slot),issue:el.value||'missing'});persist();toast('Masukan wajah tersimpan.');}
    }catch(error){const errorEl=$('#upload-error');if(errorEl)errorEl.textContent=error.message;else toast(error.message);const status=$('#upload-status');if(status)status.textContent='Foto sebelumnya tetap tersimpan.';}
  });
  document.addEventListener('focusout',e=>{
    if(e.target.matches('textarea[minlength]')&&e.target.value&&e.target.value.trim().length<Number(e.target.minLength)){const field=e.target.closest('.field')?.querySelector('.field-error');if(field)field.textContent='Ceritakan sedikit lagi, ya. Minimal '+e.target.minLength+' karakter supaya kami bisa bantu.';}
  });
  window.addEventListener('hashchange',()=>{closeModal();selectedFace=0;pageLimit=24;render();});
  $('#dialog').addEventListener('cancel',()=>{uploadSerial++;uploadContext=null;});
  window.addEventListener('pageshow',()=>{if(db&&M.tick(state)){persist();render(true);}});
  init();
})();
