(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const date = value => new Intl.DateTimeFormat('id-ID', {dateStyle:'long', timeStyle:'short', timeZone:'Asia/Jakarta'}).format(new Date(value));
  const money = value => 'Rp' + new Intl.NumberFormat('id-ID').format(value);
  const activeStates = ['queued', 'dispatching', 'processing', 'uncertain', 'finalizing'];
  const labels = {queued:'Dalam antrean', dispatching:'Menyiapkan foto', processing:'Membuat foto', uncertain:'Masih menunggu kabar', finalizing:'Menyiapkan hasil', ready:'Siap dilihat', failed:'Proses belum berhasil', cancelled:'Proses dibatalkan', expired:'Kedaluwarsa', deleted:'Dihapus', waiting:'Menunggu balasan', action_required:'Menunggu jawabanmu', resolved:'Selesai', refund_progress:'Lagi kami bantu'};
  const state = {session:null, templates:[], offers:[], projects:[], selectedTemplate:null, selectedProject:null, admission:false, toastTimer:null, pollTimer:null, projectRead:0, busy:false, query:'', people:'', occasion:'', university:'', catalogMoment:null, catalogReturn:null, catalogStates:new Map(), catalogScroll:new Map(), renderedRoute:null, nextOffset:null, loadingProject:null, projectErrors:new Map(), connectionError:'', publicErrors:new Map(), keys:new Map()};
  const moments = [
    {id:'hari-raya', name:'Hari raya & perayaan', description:'Hari spesial makin seru kalau bareng orang tersayang.', occasions:['Lebaran','Natal','Imlek','Ramadan','Idul Adha','Galungan','Waisak','Hari Kemerdekaan','Tahun Baru'], cover:'lebaran', color:'lime'},
    {id:'wisuda', name:'Wisuda', description:'Akhirnya wisuda! Yuk, simpan momen banggamu.', occasions:['Wisuda'], cover:'wisuda-ui', color:'lilac'},
    {id:'ulang-tahun', name:'Ulang tahun', description:'Tambah umur, tambah cerita. Saatnya foto bareng!', occasions:['Ulang Tahun'], cover:'ulang-tahun-anak', color:'peach'},
    {id:'cerita-cinta', name:'Cerita cinta', description:'Dari awal jadian sampai bertahun-tahun bareng.', occasions:['Pre-wedding','Pernikahan','Anniversary'], cover:'prewedding-taman', color:'peach'},
    {id:'si-kecil', name:'Menanti & menyambut si kecil', description:'Si kecil tumbuh cepat. Simpan momen manisnya, yuk.', occasions:['Maternity','Bayi'], cover:'bayi-enam-bulan', color:'lime'},
    {id:'keluarga', name:'Kebersamaan keluarga', description:'Hari biasa juga boleh jadi kenangan istimewa.', occasions:['Studio','Di rumah'], cover:'studio', color:'lilac'}
  ];
  function momentCollections() {
    const collections = moments.map(moment => ({...moment, items:state.templates.filter(item => moment.occasions.includes(item.occasion))}));
    const others = state.templates.filter(item => !moments.some(moment => moment.occasions.includes(item.occasion)));
    if (others.length) collections.push({id:'lainnya', name:'Momen lainnya', description:'Masih banyak momen yang bisa kamu simpan.', color:'lilac', items:others});
    return collections.filter(moment => moment.items.length);
  }
  const momentFor = template => momentCollections().find(moment => moment.items.some(item => item.id === template?.id));
  function momentCard(moment) {
    const cover = moment.items.find(item => item.slug === moment.cover) || moment.items[0];
    return `<a class="moment-card moment-${moment.color}" href="#/templates/${moment.id}"><div class="moment-art">${templateImage(cover)}<span class="photo-tag">${moment.items.length} template</span></div><div class="moment-copy"><div><h2>${esc(moment.name)}</h2><p>${esc(moment.description)}</p></div><span class="circle-link" aria-hidden="true">${icon('arrow')}</span></div></a>`;
  }
  const icon = (name, size=20) => {
    const paths = {close:'M6 6l12 12M18 6 6 18', back:'M20 12H4m6-6-6 6 6 6', zoom:'M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12Zm4 10 6 6M10 7v6M7 10h6', home:'M3 10 12 3l9 7v11h-6v-7H9v7H3Z', grid:'M3 3h7v7H3Zm11 0h7v7h-7ZM3 14h7v7H3Zm11 0h7v7h-7Z', photo:'M3 4h18v16H3ZM3 16l6-6 5 5 3-3 4 4M16 8h.01', book:'M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-2-10 1Zm0 0v16', help:'M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', arrow:'M4 12h16m-6-6 6 6-6 6', shield:'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6Zm-5 10 3 3 7-7', check:'m5 12 4 4L19 6', plus:'M12 5v14M5 12h14', download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5'};
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]?`<path d="${paths[name]}"/>`:''}</svg>`;
  };
  const brand = `MomenRia<span class="brand-dot">.</span>`;
  const route = () => location.hash.replace(/^#/, '') || '/';
  const parts = () => route().split('/').filter(Boolean);
  const go = path => { if (route() === path) render(); else location.hash = path; };
  const activeJob = project => project?.jobs.find(job => activeStates.includes(job.state));
  const validSource = source => source?.status === 'ready' && Date.parse(source.expires_at) > Date.now();
  const validResult = result => result?.status === 'ready' && Date.parse(result.expires_at) > Date.now();
  const currentResult = project => project.results.find(result => result.id === project.selected_result_id) || project.results.at(-1);
  const studioPath = (template, project) => `/studio/${template.id}${project?`/${project.id}`:''}`;
  const projectTemplate = project => project.template || state.templates.find(template => template.id === project.template_id);
  const badge = text => `<span class="tag">${esc(text)}</span>`;
  const notice = text => `<div class="notice">${icon('help')}<p>${text}</p></div>`;
  const pageHeading = (eyebrow, title, description) => `<div class="page-heading"><h1>${title}</h1><p class="lede">${description}</p></div>`;
  const empty = (title, text, href='/templates', action='Cari template') => `<div class="empty"><span class="empty-icon">${icon('photo',32)}</span><h2>${title}</h2><p>${text}</p><a class="btn primary" href="#${href}">${action}${icon('arrow')}</a></div>`;
  const loginPrompt = text => empty('Foto keluargamu menunggu di sini', text, '/templates', 'Lihat template') + `<p class="center"><a class="btn primary" href="/accounts/login/?next=${encodeURIComponent('/#'+route())}">Masuk ke akun</a> <a class="text-link" href="/accounts/signup/">Buat akun</a></p>`;
  function remember(key, value) { try { if (value === undefined) return sessionStorage.getItem(key); sessionStorage.setItem(key, value); } catch {} return null; }
  function requestKey(action, id, revision) {
    const key = `${action}:${id}:${revision}`;
    if (!state.keys.has(key)) state.keys.set(key, crypto.randomUUID());
    return state.keys.get(key);
  }

  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    if (!['GET','HEAD'].includes(options.method || 'GET') && state.session?.csrf_token) headers.set('X-CSRFToken', state.session.csrf_token);
    let response;
    try { response = await fetch(path, {...options, headers, credentials:'same-origin'}); }
    catch { throw Error('Koneksi putus. Cek internetmu, lalu coba lagi, ya. Foto yang sudah tersimpan tetap ada.'); }
    const payload = (response.headers.get('content-type') || '').includes('application/json') ? await response.json() : null;
    if (!response.ok) throw Object.assign(Error(payload?.message || 'Belum berhasil. Coba lagi, ya.'), {status:response.status, payload});
    return payload;
  }
  function announce(message) {const node=$('#job-status'); if(node.textContent!==message) node.textContent=message;}
  function toast(message) {
    clearTimeout(state.toastTimer); $('#toast').textContent = message; $('#toast').hidden = false;
    state.toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6000);
  }
  function showDialog(title, content) {
    const dialog = $('#dialog');
    releaseUploadPreviews();
    dialog.innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-btn" data-close aria-label="Tutup">${icon('close')}</button></div><div class="dialog-body">${content}</div>`;
    dialog.showModal();
    dialog.scrollTop = 0;
    dialog.querySelector('[data-close]').focus({preventScroll:true});
  }
  function closeDialog() { $('#dialog').close(); }
  function chrome() {
    const section = parts()[0] || 'home';
    const signature=JSON.stringify([section,state.session.authenticated,state.session.public_access,state.session.capabilities?.payments_enabled]);
    if(state.chromeSignature===signature) return;
    state.chromeSignature=signature;
    const account = state.session.public_access ? '<span class="tag">Demo bersama</span>' : state.session.authenticated ? '<a class="account-link" href="/accounts/email/">Akun saya</a><a class="btn secondary small" href="/accounts/logout/">Keluar</a>' : '<a class="account-link" href="/accounts/login/">Masuk</a><a class="btn primary small" href="/accounts/signup/">Mulai gratis</a>';
    $('#header').innerHTML = `<div class="topbar-inner"><a class="brand" href="#/" aria-label="MomenRia, beranda">${brand}</a><div class="app-nav" id="app-nav"></div><div class="app-account">${state.session.capabilities?.payments_enabled?'<a class="account-link" href="#/orders">Pesanan</a>':''}${account}</div></div>`;
    const links = [['/','Beranda','home','home'],['/templates','Template','templates','grid'],['/projects','Foto saya','projects','photo'],['/guide','Panduan','guide','book'],['/support','Bantuan','support','help']];
    $('#app-nav').innerHTML = `<nav aria-label="Navigasi utama">${links.map(([href,label,key,glyph]) => { const active = key===section || key==='templates' && ['template','studio'].includes(section) || key==='projects' && section==='project'; return `<a class="nav-link ${active?'active':''}" href="#${href}" ${active?'aria-current="page"':''}>${icon(glyph)}<span>${label}</span></a>`; }).join('')}</nav>`;
    $('#demo-banner').hidden = !state.session.public_access;
  }
  function footer() {
    return `<footer class="page-footer"><a class="brand" href="#/">${brand}</a><span>Biar jauh, tetap punya foto bareng.</span><div><a href="#/privacy">Privasi</a><a href="#/terms">Ketentuan</a><a href="#/support">Bantuan</a></div><small>© ${new Date().getFullYear()} MomenRia</small></footer>`;
  }
  function templateImage(template, eager=false) {
    return `<img src="/static/${esc(template.display_asset || template.sample_asset)}" width="${template.asset_width || 1448}" height="${template.asset_height || 1086}" alt="Contoh ${esc(template.name)}, ${template.people_count} orang" ${eager?'fetchpriority="high"':'loading="lazy"'}>`;
  }
  function templateCard(template) {
    return `<article class="template-card"><a class="template-art" href="#/template/${template.id}" tabindex="-1" aria-hidden="true">${templateImage(template)}<span class="photo-tag">${template.people_count} orang</span></a><div class="template-info"><h2><a href="#/template/${template.id}">${esc(template.name)}</a></h2><p>${esc(template.description)}</p><div class="template-bottom"><span>${esc(template.attire)}</span><a class="text-link template-use" href="#${studioPath(template)}" aria-label="Pilih ${esc(template.name)}">Pakai template ${icon('arrow')}</a></div></div></article>`;
  }
  function steps(level=3) {
    return `<div class="steps-grid"><article><span class="step-number">01</span><h${level}>Pilih suasana yang pas</h${level}><p>Mau foto Lebaran, wisuda, atau bareng si kecil? Pilih template buat 1–4 orang.</p></article><article><span class="step-number">02</span><h${level}>Masukkan foto masing-masing</h${level}><p>Siapkan satu foto yang jelas buat tiap orang. Ketuk nomor wajah, lalu pilih fotonya.</p></article><article><span class="step-number">03</span><h${level}>Cek wajahnya, lalu simpan</h${level}><p>Cek tiap wajah dulu, ya. Kamu bisa koreksi satu wajah setiap proses, sebanyak yang diperlukan. Kalau sudah cocok, download preview gratis.</p></article></div>`;
  }
  function faqs() {
    return `<div class="faq-list"><details><summary>Harus punya foto bareng dulu?${icon('plus')}</summary><p>Nggak perlu! Cukup satu foto masing-masing orang. Pilih yang wajahnya jelas, menghadap kamera, dan nggak pakai filter yang mengubah wajah.</p></details><details><summary>Yang gratis dapat apa saja?${icon('plus')}</summary><p>Setelah verifikasi email, kamu bisa bikin foto dan melakukan koreksi tanpa batas jumlah. Preview dengan watermark bisa kamu download gratis. Versi master berbayar belum tersedia saat ini.</p></details><details><summary>Hasilnya bakal mirip, nggak?${icon('plus')}</summary><p>AI bisa mengubah detail wajah, jadi hasilnya belum tentu sama persis dengan foto asli. Cek semua wajah, ya, termasuk wajah lain setelah koreksi.</p></details><details><summary>Kok fotoku belum bisa dipakai?${icon('plus')}</summary><p>Coba foto dengan satu wajah yang dekat, jelas, dan terang. Hindari kacamata gelap, wajah tertutup, atau foto yang terlalu kecil. Upload JPEG atau PNG hingga ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB.</p></details><details><summary>Fotoku disimpan berapa lama?${icon('plus')}</summary><p>Foto yang kamu upload disimpan ${state.session.policy.source_retention_days} hari sejak upload; hasilnya ${state.session.policy.result_retention_days} hari sejak selesai. Download atau tambah ucapan nggak memperpanjang masa simpan. Kamu bisa hapus proyek kapan saja dari Foto saya.</p></details><details><summary>Kalau fotonya lama selesai, harus gimana?${icon('plus')}</summary><p>Proyekmu tetap tersimpan. Cek statusnya di Foto saya. Kalau statusnya belum jelas, jangan mulai ulang dulu. Hubungi Bantuan supaya kami bisa cek prosesnya.</p></details></div>`;
  }
  function home() {
    return `<div class="landing">${modeNotice()}
      <section class="hero">
        <div class="hero-copy">
          
          <h1>Lagi jauh?<br><em>Foto bareng</em><br>tetap bisa.</h1>
          <p>Belum sempat kumpul? Pakai foto masing-masing, lalu bikin foto bareng orang tersayang dengan bantuan AI.</p>
          <div class="hero-actions"><a class="btn primary" href="#/templates">Cari template ${icon('arrow')}</a><a class="text-link" href="#/guide">Lihat caranya ${icon('arrow',16)}</a></div>
          <div class="source-explainer"><div class="source-explainer-photos"><img src="/static/app/assets/photo-guide.jpg" width="80" height="80" alt="Ilustrasi foto sumber orang pertama"><img src="/static/app/assets/photo-guide-right.jpg" width="80" height="80" alt="Ilustrasi foto sumber orang kedua"></div><p><strong>Foto masing-masing → potret bersama</strong><br>Upload satu foto tiap orang, pilih posisi di template, lalu cek wajah pada hasil.<span class="caption">Ilustrasi sintetis; bukan contoh hasil atau bukti kemiripan.</span></p></div>
          <p class="hero-caption">Preview gratis · berwatermark · hingga 768 px<br>Nggak perlu kartu pembayaran</p>
        </div>
        <div class="hero-visual">
          <figure class="hero-photo hero-photo-main">
            <img src="/static/app/assets/studio.webp" alt="Contoh potret AI keluarga berempat dengan pakaian linen netral" width="1448" height="1086" fetchpriority="high">
          </figure>
          <figure class="hero-photo hero-photo-small">
            <img src="/static/app/assets/lebaran.webp" alt="Contoh potret AI pasangan dalam suasana Lebaran" width="1448" height="1086" loading="eager">
            <figcaption>Hari spesial, orang-orang favorit.</figcaption>
          </figure>
          <span class="hero-sticker" aria-hidden="true">Kumpul,<br>versi kamu.<svg viewBox="0 0 70 30" fill="none"><path d="M3 8C18 27 44 29 62 7M48 7l16-3-1 17" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
          <p class="sample-note">Ini contoh template AI, ya. Hasil fotomu bisa berbeda.</p>
        </div>
      </section>
      <div class="trust-strip"><span>${icon('photo')} Foto masing-masing, jadi foto bareng</span><span>${icon('shield')} Fotomu pribadi, aksesnya dibatasi</span><span>${icon('download')} Preview bisa didownload gratis</span></div>
      <section class="landing-section collection-section">
        <div class="section-heading"><div><h2>Pilih momennya.<br><em>Yuk, bikin fotonya.</em></h2></div><a class="text-link" href="#/templates">Lihat semua momen ${icon('arrow')}</a></div>
        ${state.templates.length?`<div class="moment-grid">${momentCollections().slice(0,3).map(momentCard).join('')}</div>`:empty('Templatenya lagi kami siapkan', 'Kami cek dulu supaya templatenya siap kamu pakai. Sambil menunggu, lihat cara bikin fotonya, yuk.', '/guide', 'Lihat cara bikin foto')}
      </section>
      <section class="landing-section how-section"><div class="section-heading"><div><h2>Tiga langkah.<br><em>Satu kenangan baru.</em></h2></div><p class="section-aside">Nggak perlu tunggu semua<br>kumpul di satu tempat.</p></div>${steps()}</section>
      <section class="privacy-feature"><figure class="privacy-art"><img src="/static/app/assets/home.webp" width="1448" height="1086" alt="Contoh potret keluarga dalam suasana rumah yang hangat" loading="lazy"><figcaption>Momen di Rumah <span>Contoh template AI</span></figcaption></figure><div><h2>Foto pribadimu,<br>kamu yang<br><em>pegang kendali.</em></h2><p>Pakai foto yang sudah kamu punya izin untuk gunakan, ya. Foto yang kamu upload punya batas simpan, dan proyeknya bisa kamu hapus kapan saja.</p><a class="text-link" href="#/privacy">Baca soal privasi foto ${icon('arrow')}</a></div></section>
      <section class="landing-section faq-section"><div><h2>Masih ada<br><em>yang bikin penasaran?</em></h2><a class="text-link" href="#/support">Butuh bantuan lain? ${icon('arrow')}</a></div>${faqs()}</section>
      <section class="closing-card"><div><h2>Mau foto bareng<br><em>siapa hari ini?</em></h2></div><a class="btn primary" href="#/templates">Yuk, bikin foto bareng ${icon('arrow')}</a></section>
      ${footer()}
    </div>`;
  }
  function filteredTemplates(items) {
    return items.filter(item => (!state.people || String(item.people_count) === state.people) && (!state.occasion || item.occasion === state.occasion) && (!state.university || item.university === state.university) && `${item.name} ${item.description} ${item.attire} ${item.occasion} ${item.university || ''} ${item.backdrop || ''}`.toLocaleLowerCase('id').includes(state.query.toLocaleLowerCase('id').trim()));
  }
  function catalogResults() {
    const collections = momentCollections(), moment = collections.find(item => item.id === parts()[1]);
    const items = filteredTemplates(moment ? moment.items : state.templates);
    const matches = collections.map(item => ({...item, items:item.items.filter(template => items.includes(template))})).filter(item => item.items.length);
    const searching = !!(state.query.trim() || state.people || state.occasion || state.university);
    return `<p class="result-count" role="status">${moment?`${items.length} template untuk ${esc(moment.name)}`:searching?`${items.length} template ditemukan`:`${matches.length} koleksi momen · ${items.length} template untuk ceritamu`}</p>${items.length?moment||searching?`<div class="template-grid">${items.map(templateCard).join('')}</div>`:`<div class="moment-grid">${matches.map(momentCard).join('')}</div>`:`<div class="empty"><h2>Belum ada template yang cocok.</h2><p>Coba kata lain atau hapus filternya, ya.</p><button class="btn secondary" data-reset-filters>Hapus filter</button></div>`}`;
  }
  function catalogView() {
    const id = parts()[1] || '', collections = momentCollections(), moment = collections.find(item => item.id === id);
    if (id && !moment) return notFound('Koleksi belum tersedia', 'Coba pilih momen lain dulu, ya.');
    const occasions = [...new Set(moment?.items.map(item => item.occasion) || [])];
    const universities = [...new Set(moment?.items.map(item => item.university).filter(Boolean) || [])].sort((a,b)=>a.localeCompare(b,'id'));
    return `<section class="page moment-page">${moment?`<a class="back-link" href="#/templates">${icon('back',16)} Semua momen</a>`:''}${pageHeading(moment?'KOLEKSI MOMENRIA':'MAU FOTO BUAT MOMEN APA?', moment?esc(moment.name):'Mau simpan momen apa?', moment?esc(moment.description):'Hari spesial atau hari biasa, sama-sama boleh. Pilih momennya, lalu cari template yang kamu suka.')}<div class="catalog-layout">${moment?`<nav class="moment-nav" aria-label="Koleksi momen"><p class="eyebrow">PILIH MOMEN</p>${collections.map(item=>`<a href="#/templates/${item.id}" ${item.id===id?'aria-current="page"':''}>${esc(item.name)}<span>${item.items.length}</span></a>`).join('')}</nav>`:''}<div class="catalog-content"><div class="catalog-filters"><label>Cari template<input class="input" id="template-search" type="search" placeholder="${moment?'Cari di koleksi ini…':'Cari momen atau kampus…'}" value="${esc(state.query)}"></label><label>Jumlah orang<select class="input" id="people-filter"><option value="">Berapa saja</option>${[1,2,3,4].map(n=>`<option value="${n}" ${state.people===String(n)?'selected':''}>${n} orang</option>`).join('')}</select></label>${occasions.length>1?`<label>Suasana<select class="input" id="occasion-filter"><option value="">Semua suasana</option>${occasions.map(value=>`<option ${state.occasion===value?'selected':''}>${esc(value)}</option>`).join('')}</select></label>`:''}${universities.length?`<label>Universitas<select class="input" id="university-filter"><option value="">Semua kampus</option>${universities.map(value=>`<option ${state.university===value?'selected':''}>${esc(value)}</option>`).join('')}</select></label>`:''}</div><div id="catalog-results">${catalogResults()}</div><p class="caption catalog-note">Gambar di sini contoh template AI. Hasil dengan fotomu bisa berbeda, ya.</p></div></div></section>${footer()}`;
  }
  function templateView(id) {
    const template = state.templates.find(item => item.id === id);
    if (!template) return notFound('Template belum tersedia', 'Template ini mungkin lagi dijeda. Coba pilih yang lain dulu, ya.');
    return `<section class="page"><a class="back-link" href="#${state.catalogReturn || `/templates/${momentFor(template)?.id || ''}`}">${icon('back',16)} ${esc(momentFor(template)?.name || 'Semua momen')}</a><div class="template-detail"><div class="detail-art">${templateImage(template,true)}<p class="caption">Contoh template AI · belum pakai fotomu</p></div><div>${badge(`${template.people_count} orang · ${template.occasion}`)}<h1>${esc(template.name)}</h1><p class="lede">${esc(template.description)}</p><dl class="detail-list">${template.university?`<div><dt>Universitas</dt><dd>${esc(template.university)}</dd></div><div><dt>Latar kampus</dt><dd>${esc(template.backdrop)}<small class="caption">Latar dan toganya ilustrasi AI, ya. Ini bukan foto lokasi asli atau template resmi kampus.</small></dd></div>`:''}<div><dt>Pakaian</dt><dd>${esc(template.attire)}</dd></div><div><dt>Siapkan fotonya</dt><dd>${template.people_count} foto, satu wajah per foto</dd></div><div><dt>Format foto</dt><dd>JPEG / PNG · maks. ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB</dd></div><div><dt>Yang kamu dapatkan</dt><dd>Preview gratis · JPEG berwatermark · hingga 768 px</dd></div></dl><a class="btn primary block" href="#${studioPath(template)}">Pakai template ini ${icon('arrow')}</a><p class="caption">Bikin foto dan koreksi tanpa batas jumlah setelah verifikasi email, selama layanan tersedia. AI bisa mengubah detail wajah, jadi cek dulu sebelum kamu bagikan, ya.</p></div></div></section>${footer()}`;
  }
  function selected() { return state.projects.find(item=>item.id===state.selectedProject)?.template || state.templates.find(item => item.id === state.selectedTemplate); }
  function matchingProject(template) {
    if (!template) return null;
    if (state.selectedProject) return state.projects.find(project => project.id === state.selectedProject && project.template_id === template.id) || null;
    return state.projects.find(project => project.template_id === template.id && !project.results.length && !activeJob(project)) || null;
  }
  function sourceFor(project, slot) { return project?.sources.find(source => source.id === project.assignments[slot.id]); }
  function characterReferences(project, template) {
    if (!project || !template.character_references?.enabled) return '';
    const cards=template.slots.map(slot=>{
      const source=sourceFor(project,slot);
      if (!validSource(source)) return '';
      const sheets=(project.character_sheets || []).filter(sheet=>sheet.source_id===source.id && Date.parse(sheet.expires_at)>Date.now());
      const review=sheets.find(sheet=>sheet.status==='review'), selected=sheets.find(sheet=>sheet.id===project.assigned_sheets?.[slot.id]);
      const preparing=sheets.some(sheet=>sheet.status==='preparing');
      const label=review?`Cek kemiripan wajah ${slot.position}`:`Lihat referensi wajah ${slot.position}`;
      return `<article class="character-reference"><div><strong>Referensi wajah ${slot.position}</strong><p class="caption">${preparing?'Menyiapkan referensi…':review?'Cek kemiripan sebelum dipakai':selected?.mode==='generated'?'Multi-sudut disetujui':'Foto asli + detail wajah'}</p></div><button class="text-link" data-character-slot="${slot.id}" data-project="${project.id}">${label}</button></article>`;
    }).join('');
    return cards?`<details class="character-references"><summary>Referensi karakter · opsional</summary><p class="caption">Foto asli sudah cukup untuk mulai. Sudut tambahan adalah perkiraan AI; gunakan hanya setelah kamu cek kemiripannya.</p>${cards}</details>`:'';
  }
  function characterDialog(projectId, slotId) {
    const project=state.projects.find(item=>item.id===projectId), slot=project?.template.slots.find(item=>item.id===slotId);
    const source=slot && sourceFor(project,slot);
    if (!validSource(source)) throw Error('Foto asli sudah tidak tersedia. Upload ulang dulu, ya.');
    const sheets=(project.character_sheets || []).filter(sheet=>sheet.source_id===source.id && Date.parse(sheet.expires_at)>Date.now() && (sheet.mode!=='generated' || project.template.character_references?.generated_enabled));
    const review=sheets.find(sheet=>sheet.status==='review');
    const sheet=review || sheets.find(item=>item.id===project.assigned_sheets?.[slotId]);
    const generated=sheets.filter(item=>item.mode==='generated'), busy=!!activeJob(project) || !!project.results.length;
    const available=project.template.character_references?.generated_enabled && !review && !busy && generated.length<2 && !generated.some(item=>['preparing','approved'].includes(item.status));
    const controls=review?`<button class="btn primary" data-review-sheet="${review.id}" data-decision="approve" data-project="${projectId}" data-slot="${slotId}">Sudah mirip</button><button class="btn secondary" data-review-sheet="${review.id}" data-decision="reject" data-project="${projectId}" data-slot="${slotId}">Belum mirip</button>`:'';
    const alternate=sheets.filter(item=>item.status==='approved' && item.id!==project.assigned_sheets?.[slotId]);
    showDialog(`Referensi wajah ${slot.position}`, `<div class="character-comparison"><figure><img src="${source.thumbnail_url}" alt="Foto asli wajah ${slot.position}"><figcaption>Foto asli</figcaption></figure><figure>${sheet?.preview_url?`<img src="${sheet.preview_url}" alt="Referensi karakter wajah ${slot.position}">`:'<p>Referensi sedang disiapkan.</p>'}<figcaption>Referensi karakter</figcaption></figure></div><p>Bandingkan bentuk wajah, mata, hidung, rambut, dan ciri khasnya dengan foto asli.</p>${sheet?.mode==='generated'?`<p class="caption">Sudut lain merupakan perkiraan AI. Tolak kalau wajahnya berubah.${sheet.synthetic?' Ini simulasi untuk mencoba alur, bukan bukti kualitas AI.':''}</p>`:''}<div class="character-actions">${controls}${available?`<button class="btn secondary" data-generate-sheet="${source.id}" data-project="${projectId}">Buat referensi multi-sudut</button><p class="caption">Tambahan sudut AI perlu dicek dulu. Tersedia ${2-generated.length} percobaan lagi.</p>`:''}${!review&&!busy?alternate.map(item=>`<button class="text-link" data-use-sheet="${item.id}" data-project="${projectId}" data-slot="${slotId}" data-source="${source.id}">${item.mode==='source_layout'?'Pakai referensi foto asli':'Pakai multi-sudut yang disetujui'}</button>`).join(''):''}</div><p class="caption">Disimpan sampai ${date(source.expires_at)}, sama dengan foto asli.</p>`);
  }
  function faceBox(result, slot) {
    const width=result.output?.width || 2048, height=result.output?.height || 1536, side=Math.min(width,height)*.32;
    const x=Math.max(0,Math.min(width-side,slot.x*width-side/2)), y=Math.max(0,Math.min(height-side,slot.y*height-side/2));
    return {width,height,viewBox:`${x} ${y} ${side} ${side}`};
  }
  function correctionIssue(project,result) {
    if (!result.references.every(reference=>reference.thumbnail_url && Date.parse(reference.expires_at)>Date.now())) return 'Masa simpan foto aslinya sudah habis. Untuk koreksi lagi, buat proyek baru dan upload ulang foto yang kamu izinkan. Hasil ini tetap bisa didownload sampai masa simpannya habis.';
    if (!state.session.capabilities.corrections_enabled) return 'Koreksi belum bisa dipakai. Kamu masih bisa cek dan download hasilnya.';
    if (!state.admission) return 'Koreksi lagi dijeda. Hasil sebelumnya tetap ada.';
    if (activeJob(project)) return 'Koreksinya lagi dikerjakan. Hasil sebelumnya tetap bisa didownload.';
    if (project.template.status!=='published') return 'Template ini sedang dijeda. Hasil sebelumnya tetap bisa didownload.';
    return '';
  }
  function faceComparison(resultId, slotId) {
    const project=state.projects.find(item=>item.results.some(result=>result.id===resultId)), result=project.results.find(item=>item.id===resultId);
    const slot=project.template.slots.find(item=>item.id===slotId), reference=result.references.find(item=>item.slot_id===slotId);
    const width=result.output?.width || 2048, height=result.output?.height || 1536;
    const side=Math.min(width,height)*.32, x=Math.max(0,Math.min(width-side,slot.x*width-side/2)), y=Math.max(0,Math.min(height-side,slot.y*height-side/2));
    showDialog(`Bandingkan wajah ${slot.position}`, `<div class="character-comparison"><figure>${reference?.thumbnail_url?`<img src="${reference.thumbnail_url}" alt="Foto asli wajah ${slot.position}">`:'<p>Foto asli tidak tersedia.</p>'}<figcaption>Foto asli</figcaption></figure><figure><svg viewBox="${x} ${y} ${side} ${side}" role="img" aria-label="Wajah ${slot.position} di hasil"><image href="/api/v1/results/${resultId}/preview" width="${width}" height="${height}"/></svg><figcaption>Wajah di hasil</figcaption></figure></div><p>Bandingkan identitas dan ciri wajah, bukan pakaian atau cahaya. Cek juga orang lain setelah koreksi.</p><div class="character-actions"><button class="btn primary" data-face-feedback="true" data-result="${resultId}" data-slot="${slotId}">Sudah mirip</button><button class="btn secondary" data-face-feedback="false" data-result="${resultId}" data-slot="${slotId}">Belum mirip</button><button class="text-link" data-face-feedback="wrong" data-result="${resultId}" data-slot="${slotId}">Orang tidak sesuai</button></div>`);
  }
  function versionComparison(resultId) {
    const project=state.projects.find(item=>item.results.some(result=>result.id===resultId));
    const versions=project.results.filter(validResult).sort((a,b)=>a.number-b.number), current=versions.find(item=>item.id===resultId), previous=versions.filter(item=>item.id!==resultId).at(-1);
    if (!current || !previous) return;
    const pane=(label,chosen)=>`<figure><label>${label}<select class="input" data-compare-version>${versions.map(item=>`<option value="${item.id}" ${item.id===chosen.id?'selected':''}>Versi ${item.number}${item.kind==='greeting'?' · Ucapan':item.kind==='correction'?' · Koreksi':''}</option>`).join('')}</select></label><img src="/api/v1/results/${chosen.id}/preview" alt="${label}: versi ${chosen.number}" data-compare-image><svg data-compare-crop hidden role="img" aria-label="Detail versi ${chosen.number}"><image data-crop-image href="/api/v1/results/${chosen.id}/preview"/></svg></figure>`;
    showDialog('Bandingkan versi', `<p>Bandingkan wajah di posisi yang sama. Pilihan hasilmu tetap tersimpan.</p><label>Bagian foto<select class="input" id="compare-face" data-project="${project.id}"><option value="">Seluruh foto</option>${project.template.slots.map(slot=>`<option value="${slot.id}">Wajah ${slot.position}</option>`).join('')}</select></label><div class="version-comparison">${pane('Pembanding',previous)}${pane('Hasil pilihan',current)}</div><p class="caption">Detail diperbesar dari preview berwatermark, tanpa menambah ketajaman. Gunakan pemilih wajah dan versi dengan keyboard; versi sebelumnya tetap utuh.</p>`);
    if (window.matchMedia('(max-width:600px)').matches) $('#compare-face').value=project.template.slots[0].id;
    updateVersionCrops();
  }
  function updateVersionCrops() {
    const picker=$('#compare-face'), project=state.projects.find(item=>item.id===picker.dataset.project), slot=project.template.slots.find(item=>item.id===picker.value);
    document.querySelectorAll('.version-comparison figure').forEach(figure=>{
      const chosen=project.results.find(item=>item.id===figure.querySelector('select').value), image=figure.querySelector('[data-compare-image]'), svg=figure.querySelector('[data-compare-crop]'), crop=svg.querySelector('image');
      image.hidden=!!slot; svg.toggleAttribute('hidden',!slot);
      if(slot) {const box=faceBox(chosen,slot); svg.setAttribute('viewBox',box.viewBox);svg.setAttribute('aria-label',`Detail wajah ${slot.position}, versi ${chosen.number}`);crop.setAttribute('width',box.width);crop.setAttribute('height',box.height);crop.setAttribute('href',image.src);}
    });
  }
  function exportDialog(resultId) {
    showDialog('Simpan foto', `<p>Semua wajah tetap masuk. Bingkai ditambahkan agar foto pas; wajah dan ucapan nggak dibuat ulang.</p><div class="export-layout"><img id="export-preview" src="/api/v1/results/${resultId}/preview" alt="Preview format yang akan didownload"><div><label for="export-format">Format foto</label><select class="input" id="export-format" data-result="${resultId}"><option value="original">Asli · hingga 768 px</option><option value="square">Persegi 1:1 · 768 × 768 px</option><option value="portrait">Potret 3:4 · 576 × 768 px</option><option value="story">Story / Status 9:16 · 432 × 768 px</option></select><p class="caption">JPEG berwatermark untuk berbagi digital. Bingkai tidak menambah detail foto. Masa simpan tetap sama.</p><a class="btn primary block" id="export-download" href="/api/v1/results/${resultId}/preview?download=1" download>${icon('download')} Download preview</a></div></div>`);
  }
  function releaseUploadPreviews() {
    document.querySelectorAll('[data-upload-preview]').forEach(image => URL.revokeObjectURL(image.src));
  }
  function batchUploadDialog() {
    const template = selected(), project = matchingProject(template);
    const slots = template.slots.filter(slot => !validSource(sourceFor(project, slot)));
    if (!slots.length || activeJob(project) || project?.results.length) return;
    if (!state.session.authenticated || !state.session.email_verified) { uploadDialog(slots[0].id); return; }
    showDialog('Tambahkan beberapa foto', `<form class="server-form" id="batch-upload-form" data-template="${template.id}" ${project?`data-project="${project.id}"`:''}><p>Pilih hingga ${slots.length} foto sekaligus, satu orang per foto. Cocokkan tiap foto dengan nomor wajah sebelum menyimpan.</p>${modeNotice()}${photoGuidance()}<div class="batch-template portrait-canvas">${templateImage(template)}${template.slots.map(slot => `<span class="batch-marker" style="--x:${slot.x*100}%;--y:${slot.y*100}%">${slot.position}</span>`).join('')}</div><label>Foto untuk keluarga<input class="input" type="file" id="batch-files" accept="image/jpeg,image/png" multiple required></label><p class="caption">JPEG / PNG · maks. ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB per foto · disimpan ${state.session.policy.source_retention_days} hari. Foto belum dikirim sebelum kamu menyimpan.</p><div id="batch-review"></div><label class="check"><input type="checkbox" name="consent" required><span>Aku punya hak atau izin untuk memakai semua foto ini dalam pembuatan foto AI, termasuk izin wali yang berwenang untuk foto anak, dan memahami <a href="#/privacy" data-dialog-link>masa simpan foto</a>.</span></label><p class="form-error" role="alert" tabindex="-1" hidden></p><p id="batch-status" role="status"></p><button class="btn primary" type="submit" disabled>Cek dan pasang semua foto</button></form>`);
  }
  function reviewBatchFiles(input) {
    const form = input.form, files = [...input.files];
    const project = state.projects.find(item => item.id === form.dataset.project), template = project?.template || selected();
    const slots = template.slots.filter(slot => !validSource(sourceFor(project, slot)));
    releaseUploadPreviews(); form.batchUploads = []; $('#batch-review').innerHTML = ''; $('#batch-status').textContent = '';
    const error = form.querySelector('.form-error'); error.hidden = true; form.querySelector('[type="submit"]').disabled = true;
    if (!files.length) return;
    if (files.length > slots.length || files.some(file => !['image/jpeg','image/png'].includes(file.type) || file.size > state.session.policy.upload_max_bytes)) {
      error.textContent = `Pilih hingga ${slots.length} foto JPEG / PNG, maksimal ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB per foto.`; error.hidden = false; return;
    }
    form.batchUploads = files.map(file => ({file, key:crypto.randomUUID()}));
    $('#batch-review').innerHTML = files.map((file, index) => `<div class="batch-row" data-batch-row="${index}"><img data-upload-preview src="${URL.createObjectURL(file)}" alt="Foto pilihan ${index + 1}"><label><span class="batch-filename">${esc(file.name)}</span><select class="input" name="slot-${index}" aria-label="Posisi foto ${index + 1}">${slots.map((slot, position) => `<option value="${slot.id}" ${position === index?'selected':''}>Wajah ${slot.position}</option>`).join('')}</select><small data-batch-message>Belum disimpan</small></label></div>`).join('');
    form.querySelector('[type="submit"]').disabled = false;
  }
  async function handleBatchUpload(form) {
    const initialRoute = route(), template = state.templates.find(item => item.id === form.dataset.template) || selected();
    const items = form.batchUploads || [];
    if (!items.length || !form.elements.consent.checked) throw Error('Pilih foto dan centang izin penggunaannya dulu, ya.');
    const slots = items.map((_, index) => form.elements[`slot-${index}`].value);
    if (new Set(slots).size !== slots.length) throw Error('Setiap foto perlu posisi wajah yang berbeda. Cek pilihannya dulu, ya.');
    let project = form.dataset.project ? await api(`/api/v1/projects/${form.dataset.project}`) : await ensureProject(template);
    form.dataset.project = project.id;
    for (const [index, item] of items.entries()) {
      const row = form.querySelector(`[data-batch-row="${index}"]`), message = row.querySelector('[data-batch-message]');
      const assigned = project.assignments[slots[index]];
      if (item.saved && assigned === item.sourceId) continue;
      if (project.template_id !== template.id || validSource(sourceFor(project, {id:slots[index]})) && assigned !== item.sourceId) throw Error('Draf berubah. Tutup pemilih foto dan cek penempatan terbaru sebelum lanjut.');
      $('#batch-status').textContent = `Memeriksa foto ${index + 1} dari ${items.length}…`;
      try {
        if (!item.sourceId) {
          const data = new FormData(); data.set('image', item.file); data.set('upload_key', item.key); data.set('consent_version', 'prd-v1'); data.set('consent_granted', 'true');
          item.sourceId = (await api(`/api/v1/projects/${project.id}/sources`, {method:'POST', body:data})).id;
        }
        if (assigned !== item.sourceId) project = await api(`/api/v1/projects/${project.id}/slots/${slots[index]}`, {method:'PUT', body:JSON.stringify({source_id:item.sourceId, expected_revision:project.revision})});
        state.projects[state.projects.findIndex(value => value.id === project.id)] = project;
        item.saved = true; form.elements[`slot-${index}`].disabled = true; message.textContent = 'Foto tersimpan';
      } catch (error) {
        message.textContent = error.message;
        $('#batch-status').textContent = `${items.filter(value => value.saved).length} dari ${items.length} foto tersimpan. Foto yang berhasil tetap aman; kamu bisa coba lagi atau pilih ulang foto yang belum berhasil.`;
        throw error;
      }
    }
    closeDialog();
    if (route() === initialRoute) { history.replaceState(null, '', `#${studioPath(template, project)}`); render(); }
    toast('Foto sudah terpasang. Cek nomor tiap wajah sebelum bikin foto, ya.');
  }
  function generationIssue(project, template) {
    if (!state.admission) return 'Bikin foto lagi dijeda. Kamu masih bisa menyiapkan draf dan buka hasil yang sudah ada.';
    if (template.status !== 'published') return 'Template ini lagi dijeda. Draf dan hasilmu tetap tersimpan, kok.';
    if (activeJob(project)) return 'Fotomu lagi dibuat. Buka proyek untuk cek perkembangannya.';
    if (!template.slots.every(slot => validSource(sourceFor(project, slot)))) return 'Tambahkan foto untuk tiap wajah dulu, ya.';
    return '';
  }
  function studio() {
    if (state.selectedProject && state.session.authenticated && !state.projects.some(item=>item.id===state.selectedProject)) {
      const error=state.projectErrors.get(state.selectedProject);
      return error?`<section class="page">${notice(esc(error))}<button class="btn secondary" data-retry-project="${esc(state.selectedProject)}">Coba buka lagi</button><a class="text-link" href="#/projects">Foto saya</a></section>`:'<section class="page"><p role="status">Membuka draf…</p></section>';
    }
    const template = selected();
    if (!template) return notFound('Pilih template dulu, yuk', 'Cari suasana yang kamu suka dan jumlah orang yang pas.');
    const project = matchingProject(template), ready = template.slots.filter(slot => validSource(sourceFor(project, slot))).length;
    const frozen = !!activeJob(project) || !!project?.results.length, issue = generationIssue(project, template);
    const action = ready < template.people_count && !frozen ? template.people_count>1?'<button class="btn primary block" data-batch-upload>Tambah beberapa foto sekaligus</button>':`<button class="btn primary block" data-upload-slot="${template.slots[0].id}">Tambahkan foto</button>`:'';
    return `<section class="studio"><div class="studio-toolbar"><div><a class="back-link" href="#${state.catalogReturn || `/templates/${momentFor(template)?.id || ''}`}">${icon('back',16)} Koleksi momen</a><h1>${esc(template.name)}</h1><p>${template.people_count} orang · ${esc(template.attire)}</p></div>${badge(project?'Draf tersimpan':'Mulai dari fotomu')}</div>${journey(ready===template.people_count?2:1)}${modeNotice()}<div class="studio-grid"><div class="studio-preview"><div class="preview-heading"><span>Posisi wajah</span>${badge(`${ready} / ${template.people_count} foto siap`)}</div><div class="portrait-canvas">${templateImage(template,true)}${template.slots.map(slot=>{const source=sourceFor(project,slot), valid=validSource(source); return `<button class="face-target ${valid?'ready':''}" style="--x:${slot.x*100}%;--y:${slot.y*100}%" data-upload-slot="${slot.id}" aria-label="${valid?'Ganti':'Tambahkan'} foto wajah ${slot.position}" ${frozen?'disabled':''}>${valid&&source.thumbnail_url?`<img src="${source.thumbnail_url}" alt="">`:''}<span>${slot.position}</span></button>`;}).join('')}</div><div class="studio-stage-note">${icon('photo')}<p>Nomor menunjukkan posisi orang. Foto yang sudah dipasang muncul langsung di posisi itu. Ini masih contoh template; potret baru dibuat setelah diproses.</p></div><button class="text-link" data-change-template ${project && !project.template_change_available?'disabled':''}>Ganti template ${icon('grid',16)}</button><a class="text-link" href="#/guide">Tips pilih foto ${icon('arrow')}</a></div><aside class="studio-controls"><div><h2>${ready===template.people_count?'Cek posisi, lalu buat':'Tambahkan foto'}</h2><p class="muted">Satu foto yang jelas buat tiap orang.</p><p class="caption">Gratis · preview JPEG berwatermark · hingga 768 px. ${state.session.policy.source_retention_days} hari untuk foto asli; ${state.session.policy.result_retention_days} hari untuk hasil.</p></div><div class="upload-progress"><span>Foto siap</span><strong>${ready} dari ${template.people_count}</strong></div><div class="studio-uploads">${template.slots.map(slot=>{const source=sourceFor(project,slot), valid=validSource(source); return `<button class="upload-tile ${valid?'ready':''}" data-upload-slot="${slot.id}" ${frozen?'disabled':''}><span class="upload-thumbnail">${valid&&source.thumbnail_url?`<img src="${source.thumbnail_url}" alt="Foto terpasang pada wajah ${slot.position}">`:icon('plus')}</span><span><strong>Wajah ${slot.position}</strong><small>${valid?'Foto siap · ketuk untuk ganti':source?'Masa simpan habis · upload ulang':'Pilih foto JPEG / PNG'}</small></span><span class="upload-index">${slot.position}</span></button>`;}).join('')}</div>${project?.revision>1&&!frozen?'<button class="text-link undo" data-undo>Batalkan perubahan terakhir</button>':''}${characterReferences(project,template)}<div class="studio-submit">${action}<button class="btn ${action?'secondary':'primary'} block" data-generate ${issue?'disabled':''}>${template.people_count===1?'Buat potret':'Buat foto keluarga'} ${icon('arrow')}</button><p class="generation-hint">${issue || 'Semua foto siap. Pastikan tiap nomor berisi orang yang tepat.'}</p>${project?`<a class="text-link" href="#/project/${project.id}">Buka proyek ${icon('arrow')}</a>`:''}</div><p class="caption">Dengan melanjutkan, kamu menyetujui <a href="#/terms">ketentuan penggunaan</a>. Koreksi tanpa batas jumlah selama layanan tersedia; AI bisa mengubah wajah.</p></aside></div></section>`;
  }
  function journey(step) {
    const names=['Template','Foto','Posisi & buat','Cek wajah','Simpan'];
    return `<nav class="journey" aria-label="Langkah pembuatan"><ol>${names.map((name,index)=>`<li ${index===step?'aria-current="step"':''}><span aria-hidden="true">${index+1}</span>${name}</li>`).join('')}</ol></nav>`;
  }
  function modeNotice() {
    if (state.session.public_access) return notice('<strong>Demo bersama.</strong> Pakai foto contoh saja; semua pengunjung bisa melihat dan menghapus data demo.');
    if (state.session.operating_mode?.synthetic_processing) return notice('<strong>Simulasi pemrosesan.</strong> Gunakan foto contoh untuk mencoba alur. Hasil ini bukan bukti kemiripan atau kesiapan layanan untuk foto pribadi.');
    return '';
  }
  function faceReview(result, slotId) {
    return (result.feedback || []).filter(item=>item.slot_id===slotId || item.slot_id===null).sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0];
  }
  function reviewLabel(result, slotId) {
    const review=faceReview(result,slotId);
    return review?.accepted===true?'Sudah sesuai':review?.accepted===false?'Perlu koreksi':'Belum dicek';
  }
  function projectCard(project) {
    const template=projectTemplate(project), result=currentResult(project), job=activeJob(project);
    return `<article class="template-card"><a class="template-art" href="#/project/${project.id}" tabindex="-1" aria-hidden="true">${validResult(result)?`<img src="/api/v1/results/${result.id}/preview" alt="" width="768" height="576" loading="lazy">`:templateImage(template)}<span class="photo-tag">${job?labels[job.state]:result?validResult(result)?`Versi ${result.number}`:'Hasil kedaluwarsa':'Draf'}</span></a><div class="template-info"><h2>${esc(template.name)}</h2><p>${result?`Disimpan sampai ${date(result.expires_at)}`:`${Object.keys(project.assignments).length} dari ${template.people_count} wajah terpasang`}</p><a class="btn secondary block" href="#/project/${project.id}">${job?'Cek proses':!result?'Lanjutkan draf':validResult(result)?'Cek & simpan':'Buka masa simpan'} ${icon('arrow')}</a></div></article>`;
  }
  function projectsView() {
    const groups=[['Sedang diproses', project=>!!activeJob(project)],['Lanjutkan draf', project=>!activeJob(project)&&!project.results.length],['Siap dilihat', project=>!activeJob(project)&&validResult(currentResult(project))],['Masa simpan berakhir', project=>!activeJob(project)&&project.results.length&&!validResult(currentResult(project))]];
    return `<section class="page workspace-page">${pageHeading('', 'Foto saya', 'Lanjutkan draf, cek proses, atau simpan hasil sebelum masa simpannya habis.')}${!state.session.authenticated?loginPrompt('Masuk untuk melihat draf dan hasil yang tersimpan di akunmu.'):state.projects.length?groups.map(([name,match])=>{const items=state.projects.filter(match); return items.length?`<section class="project-group"><h2>${name} <span class="caption">${items.length}</span></h2><div class="template-grid">${items.map(projectCard).join('')}</div></section>`:'';}).join(''):empty('Belum ada foto. Bikin yang pertama, yuk!', 'Pilih template yang kamu suka, lalu tambahkan foto orang tersayang.')}${state.nextOffset!==null?'<button class="btn secondary" data-more-projects>Lihat proyek sebelumnya</button>':''}</section>${footer()}`;
  }
  function jobNotice(project) {
    const job=project.jobs[0];
    if (!job || job.state === 'ready') return '';
    const text = {queued:'Fotomu lagi antre. Kamu boleh tutup halaman ini dan cek lagi lewat Foto saya.', dispatching:'Fotonya lagi kami siapkan. Nggak perlu kirim ulang, ya.', processing:'Kami lagi bikin fotomu. Status di halaman ini akan berubah otomatis.', uncertain:'Kami masih menunggu kabar dari layanan AI. Hasil sebelumnya tetap ada. Jangan mulai ulang dulu, ya. Hubungi Bantuan supaya kami bisa cek.', finalizing:'Sebentar, kami rapikan dan cek dulu hasilnya.', failed:'Fotonya belum berhasil dibuat. Foto dan hasil sebelumnya tetap tersimpan. Cek draf atau hubungi Bantuan sebelum coba lagi, ya.', cancelled:'Prosesnya dibatalkan. Kamu bisa cek draf atau hubungi Bantuan.'};
    return notice(`<strong>${job.operation==='character_sheet'?'Referensi karakter · ':''}${labels[job.state]}</strong>${job.updated_at?`<br><small>Diperbarui ${date(job.updated_at)}</small>`:''}<br>${text[job.state] || 'Hubungi Bantuan supaya kami bisa cek prosesnya.'}${job.error_code?`<br><small>Kode bantuan: ${esc(job.error_code)}</small>`:''}`);
  }
  function projectView(id) {
    if (!state.session.authenticated) return `<section class="page">${loginPrompt('Masuk dengan akun pemilik untuk membuka proyek ini.')}</section>`;
    const project=state.projects.find(item=>item.id===id);
    if (!project && state.loadingProject===id) return `<section class="page"><p role="status">Membuka proyek…</p></section>`;
    if (!project && state.projectErrors.has(id)) return `<section class="page">${notice(esc(state.projectErrors.get(id)))}<button class="btn secondary" data-retry-project="${esc(id)}">Coba buka lagi</button><a class="text-link" href="#/projects">Foto saya</a></section>`;
    if (!project) return notFound('Proyek tidak ditemukan', 'Proyek mungkin sudah dihapus atau tersimpan di akun lain.', '/projects', 'Kembali ke Foto saya');
    const template=projectTemplate(project), result=currentResult(project), busy=!!activeJob(project);
    const actions=`<div class="project-links"><a class="text-link" href="#/support/${project.id}">Bantuan untuk proyek ini ${icon('arrow')}</a><button class="text-link danger-text" data-delete-project="${project.id}">Hapus proyek</button></div>`;
    if (!result) return `<section class="page"><a class="back-link" href="#/projects">${icon('back',16)} Foto saya</a>${pageHeading(busy?'FOTO SEDANG DIPROSES':'DRAF TERSIMPAN', esc(template.name), 'Foto yang sudah kamu pasang tetap tersimpan sampai batas waktunya, ya.')}${jobNotice(project)}<div class="draft-detail"><div class="detail-art">${templateImage(template)}</div><div><h2>${Object.keys(project.assignments).length} dari ${template.people_count} wajah terpasang</h2><p>Cek posisi tiap foto sebelum lanjut, ya.</p><a class="btn primary" href="#${studioPath(template,project)}">${busy?'Lihat penempatan':'Lanjutkan draf'} ${icon('arrow')}</a>${actions}</div></div></section>`;
    if (!validResult(result)) return `<section class="page"><a class="back-link" href="#/projects">${icon('back',16)} Foto saya</a>${pageHeading('MASA SIMPAN BERAKHIR', 'Hasil sudah kedaluwarsa', `Hasil ini tersedia sampai ${date(result.expires_at)}. Foto yang kedaluwarsa tidak bisa dipulihkan, didownload atau dikoreksi. Kamu bisa mulai proyek baru dan upload ulang foto yang diizinkan.`)}<a class="btn primary" href="#${studioPath(template)}">Buat proyek baru ${icon('arrow')}</a>${actions}</section>`;
    const correctionMessage=correctionIssue(project,result), correctionReady=!correctionMessage;
    return `<section class="page result-page workspace-page"><a class="back-link" href="#/projects">${icon('back',16)} Foto saya</a><div class="result-heading">${pageHeading('FOTONYA SUDAH JADI!', 'Yuk, cek hasil fotomu', `Versi ${result.number} · tersedia sampai ${date(result.expires_at)}`)}${badge(result.synthetic?'Hasil simulasi AI':'Potret AI')}</div>${journey(3)}${jobNotice(project)}<div class="editor-layout"><div><button class="result-image" data-zoom="${result.id}" aria-label="Perbesar hasil foto"><img src="/api/v1/results/${result.id}/preview" width="768" height="576" alt="Preview hasil versi ${result.number}"><span>${icon('zoom',16)} Perbesar buat cek wajah</span></button>${result.synthetic?'<p class="caption">Ini hasil simulasi untuk mencoba alurnya, ya. Belum menunjukkan kualitas atau kemiripan hasil AI.</p>':''}<div class="version-list" role="group" aria-label="Versi hasil">${project.results.map(item=>`<button class="btn ${item.id===result.id?'primary':'secondary'} small" data-select-result="${item.id}" aria-pressed="${item.id===result.id}" ${!validResult(item)||busy?'disabled':''}>Versi ${item.number}${item.kind==='greeting'?' · Ucapan':''}</button>`).join('')}</div>${project.results.filter(validResult).length>1?`<button class="btn secondary" data-version-compare="${result.id}">Bandingkan versi</button>`:''}<section class="reference-list"><h2>Bandingkan dengan foto asli</h2><p class="muted">Cek semua wajah, ya, termasuk yang nggak dikoreksi.</p><div class="reference-grid">${result.references.map((reference,index)=>reference.thumbnail_url&&Date.parse(reference.expires_at)>Date.now()?`<figure><img src="${reference.thumbnail_url}" alt="Foto referensi wajah ${index+1}"><figcaption><strong>Wajah ${index+1}</strong><span class="review-state">${reviewLabel(result,reference.slot_id)}</span><small>Foto asli sampai ${date(reference.expires_at)}</small><button class="text-link" data-face-compare="${result.id}" data-slot="${reference.slot_id}">Bandingkan wajah ${index+1}</button></figcaption></figure>`:`<div class="reference-expired"><strong>Wajah ${index+1}</strong><p>Masa simpan foto asli sudah habis atau fotonya sudah dihapus.</p></div>`).join('')}</div></section>${result.output?.upscaled?`<p class="caption">Hasil penyedia ${result.output.provider_width} × ${result.output.provider_height} px diperbesar secara lokal menjadi ${result.output.width} × ${result.output.height} px. Ukuran lebih besar ini nggak menambah detail asli.</p>`:''}</div><aside class="side-panel"><h2>Wajahnya sudah cocok?</h2><p class="review-summary">${template.slots.filter(slot=>faceReview(result,slot.id)?.accepted===true).length} dari ${template.people_count} wajah sesuai · versi ${result.number}</p><p>Sebelum dibagikan, cek dulu: ada wajah yang tertukar, hilang, atau berubah?</p><button class="btn secondary block" data-feedback="true" data-result="${result.id}">${icon('check')} Semua wajah sesuai</button><div class="panel-section"><h3>Perbaiki satu wajah</h3><p class="muted">${correctionMessage || 'Pilih satu wajah untuk setiap koreksi. Versi sebelumnya tetap tersimpan.'}</p><div class="correction-actions">${template.slots.map(slot=>`<button class="btn secondary small" data-correct="${result.id}" data-slot="${slot.id}" ${correctionReady?'':'disabled'}>Wajah ${slot.position} · ${reviewLabel(result,slot.id)}</button>`).join('')}</div></div><div class="panel-section"><button class="btn secondary block" data-greeting="${result.id}" ${busy?'disabled':''}>${result.greeting?'Edit ucapan':'Tambah ucapan'}</button><button class="btn primary block save-photo" data-export="${result.id}">${icon('download')} Simpan foto</button><p class="caption">Gratis · JPEG berwatermark · hingga 768 px</p>${state.session.capabilities.payments_enabled?`<button class="btn secondary block" data-checkout="${result.id}" ${result.synthetic||busy?'disabled':''}>Beli versi ini</button>`:''}</div><a class="btn secondary block" href="#/studio/${template.id}/${project.id}">Buat versi baru ${icon('arrow')}</a>${actions}</aside></div></section>`;
  }
  function guideView() {
    return `<section class="page guide-page">${pageHeading('PANDUAN SINGKAT', 'Biar hasilnya oke, mulai dari fotonya.', 'Nggak harus foto studio, kok. Siapkan foto wajah yang jelas dan izin dari orang yang ada di foto.')}${steps(2)}${photoGuidance()}<div class="guide-grid"><article class="content-card"><span class="guide-symbol good">${icon('check')}</span><h2>Pilih foto seperti ini</h2><ul><li>Cukup satu orang di tiap foto.</li><li>Wajah menghadap kamera, mata dan wajahnya terlihat jelas.</li><li>Cahayanya merata, fotonya nggak buram.</li><li>Pakai foto asli tanpa filter yang mengubah wajah.</li><li>JPEG atau PNG, maksimal ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB.</li></ul></article><article class="content-card"><span class="guide-symbol avoid">${icon('close')}</span><h2>Yang ini jangan dulu, ya</h2><ul><li>Foto rame-rame atau kolase untuk satu wajah.</li><li>Wajah kecil, buram, terlalu gelap, atau sangat terang.</li><li>Kacamata gelap atau benda yang menutupi wajah.</li><li>Foto orang lain yang belum kamu punya izin untuk pakai.</li><li>Mulai ulang saat proses sebelumnya masih jalan.</li></ul></article></div><div class="guide-detail"><h2>Pasang fotonya satu-satu, yuk.</h2><p>Nomor di gambar menunjukkan posisi tiap orang. Ketuk nomor atau kartu Wajah, pilih fotonya, lalu beri izin pemrosesan. Cek gambar kecilnya setelah foto siap. Mau ganti suasana? Pakai Ganti template sebelum proses mulai. Setelah kamu konfirmasi, posisi wajah dikosongkan. Fotomu tetap ada dan bisa dipasang lagi lewat Foto tersimpan.</p><h2>Cek wajah tiap orang, ya.</h2><p>AI bisa mengubah detail wajah. Perbesar preview, bandingkan dengan foto asli, lalu beri masukan. Pilih satu wajah setiap kali koreksi. Kamu bisa mengulang koreksi tanpa batas jumlah.</p><h2>Jangan lupa download sebelum waktunya habis.</h2><p>Foto asli tersedia ${state.session.policy.source_retention_days} hari. Hasil tersedia ${state.session.policy.result_retention_days} hari. Meski masa simpan foto aslinya habis, hasilnya masih bisa didownload selama masa simpan hasil belum berakhir.</p><a class="btn primary" href="#/templates">Pilih template pertamamu ${icon('arrow')}</a></div></section>${footer()}`;
  }
  function privacyView() {
    const policy=state.session.policy;
    return `<section class="page prose-page">${pageHeading('FOTOMU DALAM KENDALIMU', 'Privasi dan masa simpan', 'Sebelum upload, kenali cara kami menyimpan dan menjaga fotomu, ya.')}<div class="policy-meta">Terakhir diperbarui 26 September 2026</div>${state.session.public_access?notice('<strong>Demo bersama:</strong> siapa pun yang membuka situs ini dapat melihat, mengubah, dan menghapus data demo. Jangan upload foto pribadi.'):''}<h2>Data apa saja yang kami simpan?</h2><p>Supaya proyekmu bisa berjalan, kami menyimpan email akun, foto yang kamu upload, izin pemrosesan, posisi wajah, hasil, masukan, dan pesan bantuanmu. Kamu nggak perlu mengisi nama, usia, atau hubungan keluarga orang di foto.</p><h2>Bagaimana AI memakai fotomu?</h2><p>Foto asli, referensi karakter yang dipilih, dan template dikirim ke layanan AI yang kami pakai untuk membuat atau mengoreksi foto. Referensi dari foto asli hanya menata ulang foto dan detail wajah. Referensi multi-sudut bersifat opsional, dibuat AI, dan harus kamu cek sebelum dipakai; foto asli tetap menjadi acuan utama. Jumlah dan kualitas wajah dicek di sistem MomenRia. Hasilnya bisa berbeda dari foto asli. Kami tidak membuat profil identitas wajah dari fotomu.</p><p>Sebelum menerima foto pelanggan di layanan publik, kami harus memastikan siapa penyedia AI-nya, berapa lama mereka menyimpan foto, dan bagaimana foto dihapus. ${state.session.operating_mode?.synthetic_processing?'Pemrosesan saat ini berupa simulasi; gunakan foto contoh untuk menguji alur.':state.session.public_access?'Demo bersama ini hanya untuk foto contoh, bukan foto pribadi.':'Peluncuran untuk foto pribadi tetap menunggu bukti dan persetujuan operasional; antarmuka ini tidak membuktikan kesiapan penyedia.'}</p><h2>Sudah punya izin untuk pakai fotonya?</h2><p>Pakai foto milikmu atau foto yang memang kamu punya hak untuk izinkan penggunaannya. Untuk foto anak, harus ada kewenangan orang tua atau wali, dan layanan AI-nya harus memenuhi syarat untuk memproses foto anak.</p><h2>Berapa lama fotomu disimpan?</h2><ul><li>Foto asli dan thumbnail: ${policy.source_retention_days} hari sejak upload. Referensi karakter mengikuti batas simpan foto aslinya.</li><li>Hasil dan preview: ${policy.result_retention_days} hari sejak selesai.</li><li>Menambah ucapan tidak mengubah batas simpan hasil awal.</li><li>Membuka atau download foto tidak memperpanjang masa simpannya.</li></ul><h2>Siapa yang bisa lihat fotomu?</h2><p>Di layanan dengan akun pribadi, hanya kamu sebagai pemilik akun yang bisa membuka foto. Tim bantuan tidak otomatis bisa melihatnya. Kalau perlu bantuan, kamu bisa memberi satu staf akses maksimal 24 jam. Izinnya bisa kamu cabut kapan saja di halaman Bantuan.</p><h2>Mau hapus proyek?</h2><p>Buka Foto saya, pilih proyeknya, lalu pilih Hapus proyek. Setelah kamu konfirmasi, foto langsung tidak bisa diakses dan filenya masuk antrean penghapusan. Proses yang selesai belakangan tidak akan mengembalikan proyekmu. Kami bisa menyimpan catatan operasional seperlunya untuk keamanan dan menangani permintaanmu.</p><p>Menghapus foto dari cadangan dan layanan AI mengikuti prosedur pengelola dan aturan penyedia. Jadi, semua salinan file belum tentu langsung terhapus saat itu juga.</p><h2>Cookie dan pengaturan akun</h2><p>Cookie sesi membuatmu tetap masuk, sementara token keamanan melindungi tindakan di akunmu. Penyimpanan sesi browser dipakai untuk mengingat pilihan template. Kalau mau ganti email atau kata sandi, buka halaman akun.</p><h2>Masih ada pertanyaan soal privasi?</h2><p>Kirim pesan melalui <a href="#/support">Bantuan</a>. Pilih proyeknya dan ceritakan yang kamu butuhkan. Nggak perlu menyalin foto ke dalam pesan.</p></section>${footer()}`;
  }
  function termsView() {
    return `<section class="page prose-page">${pageHeading('SEBELUM MULAI, BACA DULU, YA', 'Ketentuan penggunaan', 'Ini yang perlu kamu tahu saat pakai MomenRia di tahap gratis ini.')}<div class="policy-meta">Terakhir diperbarui 26 September 2026</div><h2>Pakai foto yang sudah diizinkan</h2><p>Pastikan kamu punya hak atau izin untuk memakai foto yang kamu upload. Itu tanggung jawabmu. Jangan pakai MomenRia untuk penipuan, penyamaran yang merugikan, pelecehan, materi intim tanpa persetujuan, atau kegiatan yang melanggar hukum.</p><h2>Fotonya dibuat dengan AI</h2><p>Foto ini dibuat oleh AI, jadi bukan bukti bahwa semua orang pernah ada di tempat yang sama. Hasilnya belum tentu sama persis dengan foto asli. Cek tiap wajah dan jangan pakai hasilnya sebagai bukti kejadian nyata.</p><h2>Bikin foto dan koreksi</h2><p>Setelah verifikasi email, kamu bisa membuat foto dan melakukan koreksi tanpa batas jumlah. Satu proyek memproses satu permintaan pada satu waktu. Koreksi hanya untuk orang yang sama, bukan untuk menambah orang atau mengganti konsep. Foto aslinya harus masih dalam masa simpan, dan template serta layanan pemrosesan harus tersedia.</p><h2>Apa yang gratis saat ini?</h2><p>Kamu bisa download preview dengan watermark secara gratis. Pembelian dan download versi master berbayar belum tersedia. Nggak perlu kartu atau pembayaran untuk pakai tahap ini.</p><h2>Menyimpan dan menghapus foto</h2><p>Kamu bisa cek masa simpan di <a href="#/privacy">halaman Privasi</a> dan lihat tanggal pastinya di hasil foto. Download sebelum masa simpannya habis, ya. Proyek yang sudah dihapus tidak bisa dikembalikan lewat aplikasi.</p><h2>Kalau ada kendala</h2><p>Pembuatan atau koreksi foto bisa dijeda kalau kapasitas, biaya, atau kualitas belum memenuhi syarat. Kalau statusnya belum jelas, hubungi kami untuk cek dulu sebelum mulai ulang. Hubungi <a href="#/support">Bantuan</a> kalau ada kendala akun, proses foto, atau pertanyaan soal privasi.</p><h2>Kalau layanannya berubah</h2><p>Template dan aturan di tahap berikutnya bisa berubah. Kalau ada fitur berbayar, kami jelaskan dulu sebelum kamu bertransaksi. Ketentuan layanan publik dan informasi pengelola harus disahkan sebelum peluncuran publik.</p></section>${footer()}`;
  }
  function supportView(projectId) {
    return `<section class="page">${pageHeading('CERITA SAJA, KAMI BANTU', 'Butuh bantuan? Cerita, yuk.', 'Coba cek jawaban di bawah, atau ceritakan kendalamu. Nggak perlu kirim foto di dalam pesan, ya.')}<div class="support-layout"><section><h2>Yang sering ditanyakan</h2>${faqs()}<a class="text-link" href="#/guide">Buka panduan foto ${icon('arrow')}</a></section><section class="content-card"><h2>Ceritakan kendalamu</h2>${state.session.authenticated?`<p class="muted">Nanti balasan dan statusnya muncul di sini.</p><form class="server-form" id="support-form"><label>Topik<input class="input" name="subject" maxlength="120" required placeholder="Contoh: foto belum selesai diproses"></label><label>Proyek terkait<select class="input" name="project_id"><option value="">Tanpa proyek</option>${state.projects.map(item=>`<option value="${item.id}" ${item.id===projectId?'selected':''}>${esc(projectTemplate(item).name)} · ${item.id.slice(0,8)}</option>`).join('')}</select></label><label>Pesan<textarea class="input" name="message" minlength="10" maxlength="2000" rows="5" required placeholder="Tadi kamu sedang apa, lalu kendalanya muncul di bagian mana?"></textarea></label><label class="check"><input type="checkbox" name="image_access"><span>Aku mengizinkan satu staf melihat foto di proyek ini untuk membantu, maksimal 24 jam. Pilihan ini boleh dilewati dan izinnya bisa dicabut kapan saja.</span></label><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn primary" type="submit">Kirim pesan ${icon('arrow')}</button></form>`:'<p>Belum bisa masuk atau email verifikasi tidak sampai? Kirim permintaan akses akun tanpa login. Jangan sertakan kata sandi atau foto.</p><form class="server-form" id="account-access-form"><label>Email yang bisa dihubungi<input class="input" type="email" name="email" autocomplete="email" maxlength="254" required></label><label>Topik<input class="input" name="subject" maxlength="120" required placeholder="Contoh: verifikasi email belum sampai"></label><label>Pesan<textarea class="input" name="message" minlength="10" maxlength="2000" rows="4" required></textarea></label><p class="caption">Permintaan masuk ke antrean tim. Waktu balasan belum dijamin. Permintaan ini tidak membuka akses ke foto.</p><p class="form-error" role="alert" tabindex="-1" hidden></p><p class="receipt" role="status" hidden></p><button class="btn primary" type="submit">Kirim permintaan akun</button></form><a class="text-link" href="/accounts/login/?next=/%23/support">Masuk untuk bantuan proyek</a>'}</section></div>${state.session.authenticated?'<section class="ticket-section"><h2>Pesan saya</h2><div id="support-items" class="ticket-grid" aria-live="polite"><p>Lagi membuka pesanmu…</p></div></section>':''}</section>${footer()}`;
  }
  function notFound(title='Halaman tidak ditemukan', text='Link ini belum bisa dibuka. Coba pilih template untuk lanjut, ya.', href='/templates', action='Lihat template') { return `<section class="page">${empty(title,text,href,action)}</section>`; }
  function ordersView() { return `<section class="page">${pageHeading('RIWAYAT AKUN', 'Pesanan', 'Cek pesananmu dan download versi yang sudah kamu beli di sini.')}<div id="orders-list"><p>Lagi membuka pesananmu…</p></div></section>`; }

  function render({focus=true}={}) {
    if (!state.session || state.busy && !focus && $('#main').querySelector('[aria-busy]')) return;
    const retainedSupport=!focus && state.renderedRoute===route() && state.session.authenticated?$('#support-items'):null;
    const drafts=!focus && state.renderedRoute===route()?[...$('#main').querySelectorAll('.server-form')].map(form=>({id:form.id,fields:[...form.elements].filter(input=>input.name && input.type!=='file').map(input=>({name:input.name,value:input.value,checked:input.checked}))})):[];
    const [section, id, projectId] = parts();
    if (state.renderedRoute?.startsWith('/templates') && state.renderedRoute!==route()) {
      state.catalogReturn=state.renderedRoute;
      state.catalogStates.set(state.catalogMoment, {query:state.query,people:state.people,occasion:state.occasion,university:state.university});
      state.catalogScroll.set(state.renderedRoute,window.scrollY);
    }
    if (section==='templates' && state.renderedRoute!==route()) {
      state.catalogMoment=id || '';
      Object.assign(state, state.catalogStates.get(state.catalogMoment) || {query:'',people:'',occasion:'',university:''});
    }
    const referenceOpen=route()===state.renderedRoute && $('.character-references')?.open;
    const focused=document.activeElement, scroll=window.scrollY;
    const focusKey=focused?.id?`#${CSS.escape(focused.id)}`:focused?.name && focused.form?.id?`#${CSS.escape(focused.form.id)} [name="${CSS.escape(focused.name)}"]`:focused?.matches('a[href]')?`a[href="${CSS.escape(focused.getAttribute('href'))}"]`:focused?.matches('button,a,input,select,textarea')?[...focused.attributes].filter(attr=>attr.name.startsWith('data-')).map(attr=>`[${attr.name}="${CSS.escape(attr.value)}"]`).join(''):'';
    const inMain=$('#main').contains(focused);
    state.selectedTemplate = section==='studio'?id:null;
    state.selectedProject = section==='studio'?projectId:null;
    chrome();
    const views={templates:catalogView, template:()=>templateView(id), studio, projects:projectsView, project:()=>projectView(id), guide:guideView, support:()=>supportView(id), privacy:privacyView, terms:termsView, orders:()=>state.session.capabilities.payments_enabled?ordersView():notFound('Pembayaran belum tersedia','Saat ini kamu bisa download preview gratis. Buka Foto saya untuk ambil hasilnya.','/projects','Buka Foto saya')};
    $('#main').innerHTML = !section?home():views[section]?views[section]():notFound();
    if(retainedSupport && $('#support-items')) $('#support-items').replaceWith(retainedSupport);
    for(const draft of drafts) {const form=document.getElementById(draft.id); if(form) for(const field of draft.fields) {const input=form.elements[field.name]; if(input) {input.value=field.value; if(input.type==='checkbox') input.checked=field.checked;}}}
    if(referenceOpen && $('.character-references')) $('.character-references').open=true;
    document.title = `${({templates:'Template foto keluarga',template:state.templates.find(item=>item.id===id)?.name,studio:'Studio foto',projects:'Foto saya',project:'Hasil foto',guide:'Panduan',support:'Bantuan',privacy:'Privasi',terms:'Ketentuan',orders:'Pesanan'})[section] || 'Yuk, foto bareng'} — MomenRia`;
    if (section==='support' && state.session.authenticated && !retainedSupport) loadSupport();
    if (section==='orders' && state.session.capabilities.payments_enabled && state.session.authenticated) loadOrders();
    const connectionMessage=[...state.publicErrors.values(),state.connectionError].filter(Boolean).join(' ');
    $('#connection-status').hidden=!connectionMessage;
    $('#connection-message').textContent=connectionMessage;
    if (focus) { $('#main').focus({preventScroll:true}); window.scrollTo({top:section==='templates'?(state.catalogScroll.get(route()) || 0):0, behavior:'instant'}); }
    else if (inMain) { const replacement=focusKey && $('#main').querySelector(focusKey); (replacement && !replacement.disabled?replacement:$('#main')).focus({preventScroll:true}); window.scrollTo({top:scroll,behavior:'instant'}); }
    state.renderedRoute=route();
    const requested=section==='project'?id:section==='studio'?projectId:null;
    if (requested && state.session.authenticated && !state.projects.some(item=>item.id===requested) && state.loadingProject!==requested && !state.projectErrors.has(requested)) loadProject(requested);

  }
  async function refreshProjects({background=false}={}) {
    if (!state.session.authenticated) { state.projects=[]; return; }
    const read=++state.projectRead;
    const requested=parts()[0]==='project'?parts()[1]:parts()[0]==='studio'?parts()[2]:null;
    const [response,session]=await Promise.all([api('/api/v1/projects'),api('/api/v1/session')]);
    const ids=[...new Set([requested,...state.projects.filter(project=>activeJob(project) && !response.items.some(item=>item.id===project.id)).map(project=>project.id)].filter(Boolean))];
    const details=await Promise.all(ids.map(async id=>{try {return {id,project:await api(`/api/v1/projects/${id}`)};} catch(error) {return {id,error};}}));
    if (read!==state.projectRead || background && (state.busy || $('#dialog').open)) return false;
    const projects=response.items, removed=new Set(details.filter(item=>item.error?.status===404).map(item=>item.id));
    let connectionError='';
    for(const detail of details) {
      if(detail.project) {const index=projects.findIndex(item=>item.id===detail.id); if(index<0) projects.push(detail.project);else projects[index]=detail.project;state.projectErrors.delete(detail.id);}
      else {state.projectErrors.set(detail.id,detail.error.message);if(detail.error.status!==404) connectionError=detail.error.message;}
    }
    state.projects=[...projects.filter(item=>!removed.has(item.id)),...state.projects.filter(item=>!removed.has(item.id)&&!projects.some(fresh=>fresh.id===item.id))]; state.session=session;
    if(!background || state.nextOffset===null && state.projects.length<=50) state.nextOffset=response.next_offset ?? null;
    state.connectionError=connectionError;
    for (const project of projects) {
      if (['failed','cancelled'].includes(project.jobs[0]?.state)) {
        state.keys.delete(`creation:${project.id}:${project.revision}`);
        for (const result of project.results) state.keys.delete(`correction:${result.id}:${project.revision}`);
      }
    }
    return true;
  }
  async function loadProject(id) {
    state.loadingProject=id;
    try {
      const project=await api(`/api/v1/projects/${id}`);
      state.projects=state.projects.filter(item=>item.id!==id); state.projects.push(project); state.projectErrors.delete(id);
    } catch(error) { state.projectErrors.set(id,error.status===404?'Proyek tidak ditemukan. Cek akun pemilik atau proyek yang sudah dihapus.':error.message); }
    finally { state.loadingProject=null; if(parts().includes(id)) render({focus:false}); }
  }
  async function ensureProject(template) {
    let project=matchingProject(template);
    if (project) return project;
    if (!state.session.authenticated) throw Error('Masuk untuk menambahkan foto.');
    const offer=state.offers[0];
    if (!offer) throw Error('Belum bisa bikin draf. Coba lagi nanti, ya.');
    project=await api('/api/v1/projects',{method:'POST',body:JSON.stringify({template_id:template.id,offer_id:offer.id})});
    state.projects.unshift(project);
    return project;
  }
  function templatePicker(momentId = momentFor(selected())?.id) {
    const template = selected(), collections = momentCollections();
    const moment = collections.find(item => item.id === momentId) || collections[0];
    showDialog('Ganti template', `<div class="template-picker"><p>Mau suasana baru? Pilih momennya dulu, yuk.</p><div class="moment-tabs" role="group" aria-label="Pilih momen">${collections.map(item=>`<button class="btn secondary small" data-picker-moment="${item.id}" aria-pressed="${item.id===moment?.id}">${esc(item.name)}</button>`).join('')}</div>${moment?`<div class="picker-heading"><h3>${esc(moment.name)}</h3><span class="caption">${moment.items.length} template</span></div><div class="picker-grid">${moment.items.map(item=>`<button class="picker-template" data-pick-template="${item.id}" aria-label="${item.id===template.id?'Template aktif:':'Pilih'} ${esc(item.name)}" ${item.id===template.id?'disabled':''}>${templateImage(item)}<span><strong>${esc(item.name)}</strong><small>${item.people_count} orang${item.id===template.id?' · Sedang dipakai':''}</small></span></button>`).join('')}</div>`:'<p>Belum ada template lain yang tersedia.</p>'}</div>`);
  }
  function confirmTemplate(id) {
    const template = state.templates.find(item => item.id === id), project = matchingProject(selected());
    if (!template || template.id === selected()?.id) return;
    if (!project) { closeDialog(); go(studioPath(template)); return; }
    if (!project.template_change_available) { toast('Prosesnya sudah mulai, jadi template belum bisa diganti.'); return; }
    showDialog('Ganti ke ' + template.name + '?', `<form class="server-form" id="template-change-form" data-project="${project.id}" data-template="${template.id}" data-revision="${project.revision}"><div class="template-change-preview">${templateImage(template)}<div><strong>${esc(template.name)}</strong><p>${template.people_count} foto perlu disiapkan</p></div></div><p>Penempatan ${Object.keys(project.assignments).length} wajah akan dikosongkan. Foto yang sudah kamu upload tetap ada di proyek ini. Pasang lagi lewat <strong>Foto tersimpan</strong>.</p><p class="form-error" role="alert" tabindex="-1" hidden></p><div class="dialog-actions"><button class="btn secondary" type="button" data-picker-moment="${momentFor(template)?.id || ''}">Pilih yang lain</button><button class="btn primary" type="submit">Ganti template</button></div></form>`);
  }
  async function changeTemplate(form) {
    const initialRoute = route();
    const updated = await api(`/api/v1/projects/${form.dataset.project}`, {method:'PATCH', body:JSON.stringify({template_id:form.dataset.template, expected_revision:Number(form.dataset.revision), confirmation:'CHANGE_TEMPLATE'})});
    state.projects[state.projects.findIndex(item => item.id === updated.id)] = updated;
    closeDialog();
    if (route() === initialRoute) { history.replaceState(null, '', `#${studioPath(updated.template, updated)}`); render(); }
    toast('Templatenya sudah diganti. Ketuk wajah untuk pasang lagi foto yang tersimpan.');
  }
  function photoGuidance() {
    return `<details class="photo-guidance"><summary>Contoh foto yang mudah dipakai</summary><div class="photo-examples"><figure><img src="/static/app/assets/photo-guide.jpg" alt="Ilustrasi sintetis: satu wajah dekat dan jelas"><figcaption>${icon('check',16)} Wajah jelas, cahaya merata</figcaption></figure><figure><img class="photo-avoid" src="/static/app/assets/photo-guide.jpg" alt="Ilustrasi sintetis: wajah terlalu kecil dan buram"><figcaption>${icon('close',16)} Terlalu kecil atau buram</figcaption></figure></div><p class="caption">Ilustrasi sintetis untuk panduan input; bukan bukti hasil atau kemiripan AI.</p></details>`;
  }
  function uploadDialog(slotId) {
    if (!state.session.authenticated) { remember('momenria.pendingRoute',route()); location.href=`/accounts/login/?next=${encodeURIComponent('/#'+route())}`; return; }
    if (!state.session.email_verified) { showDialog('Verifikasi email dulu, yuk','<p>Cek inbox dan verifikasi emailmu sebelum upload foto pertama, ya.</p><a class="btn primary" href="/accounts/email/">Buka verifikasi email</a>'); return; }
    const chosenSlot=selected().slots.find(slot=>slot.id===slotId);
    showDialog('Tambahkan satu foto wajah', `<form class="server-form" id="upload-form" data-slot="${slotId}"><p><strong>Foto untuk wajah ${chosenSlot.position}</strong> · ${esc(selected().name)}</p>${modeNotice()}${photoGuidance()}<div id="single-upload-preview" hidden></div><label>Foto JPEG atau PNG<input class="input" type="file" name="image" accept="image/jpeg,image/png" aria-describedby="upload-help" required></label><p id="upload-help">Pilih foto yang jelas, cukup terang, dan cuma ada satu wajah. Maksimal ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB. Foto yang kamu upload disimpan ${state.session.policy.source_retention_days} hari sejak upload.</p><label class="check"><input type="checkbox" name="consent" required><span>Aku punya hak atau izin, termasuk kewenangan wali untuk foto anak, untuk memakai foto ini dalam pembuatan foto AI dan sudah memahami <a href="#/privacy" data-dialog-link>masa simpan foto</a>.</span></label><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn primary" type="submit">Cek dan pasang foto</button></form>`);
    const project = matchingProject(selected());
    const sources = project?.sources.filter(source => validSource(source) && !Object.values(project.assignments).includes(source.id)) || [];
    if (sources.length) $('#upload-form').insertAdjacentHTML('beforebegin', `<section class="saved-sources"><h3>Foto tersimpan</h3><p class="caption">Pilih foto yang belum dipasang. Nggak perlu upload ulang, kok.</p><div class="saved-source-grid">${sources.map((source,index)=>`<button class="saved-source" data-reuse-source="${source.id}" data-slot="${slotId}" data-project="${project.id}" data-revision="${project.revision}" aria-label="Gunakan foto tersimpan ${index+1}">${source.thumbnail_url?`<img src="${esc(source.thumbnail_url)}" alt="Foto tersimpan ${index+1}">`:icon('photo')}<span>Foto ${index+1}</span></button>`).join('')}</div></section>`);
  }
  function correctionDialog(resultId, slotId) {
    const project=state.projects.find(item=>item.results.some(result=>result.id===resultId)), result=project.results.find(item=>item.id===resultId);
    const slot=project.template.slots.find(item=>item.id===slotId), reference=result.references.find(item=>item.slot_id===slotId);
    showDialog('Perbaiki satu wajah', `<form class="server-form" id="correction-form" data-result="${resultId}" data-slot="${slotId}"><div class="correction-context">${reference?.thumbnail_url?`<img src="${reference.thumbnail_url}" alt="Foto asli wajah ${slot.position}">`:''}<div><h3>Wajah ${slot.position} · versi ${result.number}</h3><p>${reviewLabel(result,slotId)}</p></div></div><p>Koreksi orang ini saja. Setelah selesai, cek semua wajah di versi baru. Versi sebelumnya tetap bisa dibuka.</p><label>Mau diperbaiki bagaimana?<select class="input" name="operation"><option value="enhance">Bikin wajah lebih mirip</option><option value="replace_reference">Pakai foto lain dari orang yang sama</option></select></label><label data-replacement hidden>Foto pengganti<input class="input" type="file" name="image" accept="image/jpeg,image/png"></label><label class="check"><input type="checkbox" name="intent" required><span>Foto ini menampilkan orang yang sama dan aku punya hak atau izin untuk memakainya, termasuk izin wali untuk foto anak.</span></label><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn primary" type="submit">Mulai koreksi</button></form>`);
  }
  async function handleUpload(form) {
    const initialRoute = route();
    const template = selected();
    const project = await ensureProject(template);
    const data = new FormData(form);
    data.delete('consent');
    data.set('upload_key', crypto.randomUUID()); data.set('consent_version', 'prd-v1'); data.set('consent_granted', 'true');
    const source = await api(`/api/v1/projects/${project.id}/sources`, {method:'POST', body:data});
    const updated = await api(`/api/v1/projects/${project.id}/slots/${form.dataset.slot}`, {method:'PUT', body:JSON.stringify({source_id:source.id, expected_revision:project.revision})});
    state.projects[state.projects.findIndex(item=>item.id===project.id)] = updated;
    closeDialog();
    if (route() === initialRoute) { history.replaceState(null, '', `#${studioPath(template, project)}`); render(); }
    toast('Fotonya sudah terpasang!');
  }
  async function generate() {
    const initialRoute=route();
    const project=matchingProject(selected());
    if (!project) return;
    const job=await api(`/api/v1/projects/${project.id}/jobs`, {method:'POST', headers:{'Idempotency-Key':requestKey('creation',project.id,project.revision)},body:JSON.stringify({operation:'creation',expected_revision:project.revision})});
    state.keys.delete(`creation:${project.id}:${project.revision}`);
    await refreshProjects();
    if (route()===initialRoute) go(`/project/${project.id}`);
    toast(['failed','cancelled'].includes(job.state)?'Proses tadi belum berhasil. Cek draf dulu sebelum coba lagi, ya.':'Foto masuk antrean. Kamu bisa cek statusnya di Foto saya.'); schedulePoll(1500);
  }
  async function correct(form) {
    const initialRoute=route();
    const project=state.projects.find(item=>item.results.some(result=>result.id===form.dataset.result));
    const values=new FormData(form), operation=values.get('operation'), image=values.get('image');
    let replacementSourceId=null;
    if (operation==='replace_reference') {
      if (!(image instanceof File) || !image.size) throw Error('Pilih foto pengganti.');
      const upload=new FormData(); upload.set('image',image); upload.set('upload_key',crypto.randomUUID()); upload.set('consent_version','prd-v1'); upload.set('consent_granted','true');
      replacementSourceId=(await api(`/api/v1/projects/${project.id}/sources`,{method:'POST',body:upload})).id;
    }
    await api(`/api/v1/results/${form.dataset.result}/feedback`,{method:'POST',body:JSON.stringify({slot_id:form.dataset.slot,issue:'likeness',accepted:false})});
    await api(`/api/v1/results/${form.dataset.result}/corrections`,{method:'POST',headers:{'Idempotency-Key':requestKey('correction',form.dataset.result,project.revision)},body:JSON.stringify({target_slot_id:form.dataset.slot,operation,replacement_source_id:replacementSourceId,expected_revision:project.revision})});
    state.keys.delete(`correction:${form.dataset.result}:${project.revision}`);
    await refreshProjects(); closeDialog();
    if(route()===initialRoute) render();
    toast('Koreksinya masuk antrean. Hasil sebelumnya tetap ada.'); schedulePoll(1500);
  }
  async function loadSupport() {
    const node=$('#support-items');
    if (!node) return;
    try {
      const response=await api('/api/v1/support/tickets'), grants=new Map(response.grants.map(item=>[item.project_id,item]));
      if (!node.isConnected) return;
      node.innerHTML=response.items.length?response.items.map(item=>{const grant=grants.get(item.project_id); return `<article class="content-card"><div class="ticket-title"><h3>${esc(item.subject)}</h3>${badge(labels[item.status]||item.status)}</div><p class="caption">${date(item.created_at)}</p><p class="ticket-message">${esc(item.message)}</p>${item.reply?`<div class="reply"><strong>Balasan MomenRia</strong><p>${esc(item.reply)}</p></div>`:''}${(item.messages || []).map(message=>`<div class="reply owner-reply"><strong>Jawabanmu · ${date(message.created_at)}</strong><p>${esc(message.message)}</p></div>`).join('')}<details class="ticket-followup"><summary>Tambahkan jawaban</summary><form class="server-form" id="reply-${item.id}" data-reply-ticket="${item.id}"><label>Jawaban untuk ${esc(item.subject)}<textarea class="input" name="message" minlength="10" maxlength="2000" rows="3" required></textarea></label><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn secondary" type="submit">Kirim jawaban</button></form></details>${grant?`<p class="caption">Izin gambar sampai ${date(grant.expires_at)}</p><button class="btn secondary small" data-revoke-grant="${grant.id}">Cabut akses gambar</button>`:''}</article>`;}).join(''):'<p class="muted">Belum ada pesan. Kalau ada kendala, ceritakan lewat formulir di atas, ya.</p>';
    } catch(error) { if(node.isConnected) node.innerHTML=`<p class="form-error">${esc(error.message)}</p><button class="btn secondary" data-reload-support>Coba muat lagi</button>`; }
  }
  async function loadOrders() {
    const node=$('#orders-list');
    if (!node) return;
    try {
      const response=await api('/api/v1/orders');
      if (!node.isConnected) return;
      node.innerHTML=response.items.length?response.items.map(order=>`<article class="content-card"><h2>${esc(order.merchant_reference)}</h2><p>${money(order.amount)} · ${esc(order.payment_state)}</p>${order.download_url?`<a class="btn primary" href="${order.download_url}">Download master</a>`:''}</article>`).join(''):'<p>Belum ada pesanan.</p>';
    } catch(error) { if(node.isConnected) node.textContent=error.message; }
  }
  async function showError(error, form) {
    if (error.payload?.code==='stale_revision') { await refreshProjects().catch(()=>{}); }
    const node=form?.querySelector('.form-error');
    if (node) {
      node.id ||= `${form.id}-error`; node.textContent=error.message; node.hidden=false;
      const field=error.payload?.field, input=field?form.elements[field]:form.elements.image || form.querySelector('[name="message"]');
      if (input?.setAttribute) {input.setAttribute('aria-invalid','true'); input.setAttribute('aria-describedby',node.id);}
    }
    else toast(error.message);
  }
  document.addEventListener('input',event=>{
    if (event.target.name==='text' && event.target.form?.id==='greeting-form') {$('#greeting-preview').textContent=event.target.value;$('#greeting-count').textContent=event.target.value.length;}
    if (event.target.id==='template-search') {state.query=event.target.value; $('#catalog-results').innerHTML=catalogResults();}
  });
  document.addEventListener('change',event=>{
    if (event.target.name==='operation' && event.target.form?.id==='correction-form') {const replacement=event.target.form.querySelector('[data-replacement]'); replacement.hidden=event.target.value!=='replace_reference'; replacement.querySelector('input').required=!replacement.hidden;}
    if (event.target.name==='image' && event.target.form?.id==='upload-form') {
      releaseUploadPreviews(); const file=event.target.files[0], preview=$('#single-upload-preview'); preview.hidden=!file; preview.innerHTML=file?`<img data-upload-preview src="${URL.createObjectURL(file)}" alt="Foto pilihan untuk wajah ${selected().slots.find(slot=>slot.id===event.target.form.dataset.slot).position}"><p class="caption">${esc(file.name)} · belum dikirim</p>`:'';
    }
    if (event.target.id==='batch-files') reviewBatchFiles(event.target);
    if (event.target.id==='compare-face') updateVersionCrops();
    if (event.target.matches('[data-compare-version]')) { const image=event.target.closest('figure').querySelector('[data-compare-image]'); image.src=`/api/v1/results/${event.target.value}/preview`; image.alt=event.target.selectedOptions[0].textContent; updateVersionCrops(); }
    if (event.target.id==='export-format') { const url=`/api/v1/results/${event.target.dataset.result}/preview?format=${event.target.value}`; $('#export-preview').src=url; $('#export-download').href=url+'&download=1'; }
    if (['people-filter','occasion-filter','university-filter'].includes(event.target.id)) {state[event.target.id.replace('-filter','')]=event.target.value; $('#catalog-results').innerHTML=catalogResults();}
  });
  document.addEventListener('click',async event=>{
    if (event.target.closest('.skip')) {event.preventDefault(); $('#main').focus(); return;}
    const button=event.target.closest('button');
    if (event.target.closest('[data-dialog-link]')) closeDialog();
    if (!button || button.disabled || state.busy) return;
    const data=button.dataset;
    if ('close' in data) {closeDialog(); return;}
    if ('resetFilters' in data) {state.query=''; state.people=''; state.occasion=''; state.university=''; state.catalogStates.delete(state.catalogMoment); render({focus:false}); $('#template-search').focus(); return;}
    if ('changeTemplate' in data) {templatePicker(); return;}
    if ('pickerMoment' in data) {templatePicker(data.pickerMoment); return;}
    if ('pickTemplate' in data) {confirmTemplate(data.pickTemplate); return;}
    if ('batchUpload' in data) {batchUploadDialog(); return;}
    if ('versionCompare' in data) {versionComparison(data.versionCompare); return;}
    if ('export' in data) {exportDialog(data.export); return;}
    if ('uploadSlot' in data) {uploadDialog(data.uploadSlot); return;}
    if ('characterSlot' in data) {try {characterDialog(data.project,data.characterSlot);} catch(error) {await showError(error);} return;}
    if ('faceCompare' in data) {faceComparison(data.faceCompare,data.slot); return;}
    if ('correct' in data) {correctionDialog(data.correct,data.slot); return;}
    if ('zoom' in data) {showDialog('Yuk, cek kemiripan wajah',`<div class="zoom-scroll"><img src="/api/v1/results/${data.zoom}/preview" alt="Hasil foto diperbesar"></div><p class="caption">Geser gambarnya untuk cek tiap wajah. Preview hingga 768 px.</p>`); return;}
    if ('greeting' in data) {const result=state.projects.flatMap(item=>item.results).find(item=>item.id===data.greeting); showDialog('Mau tambah ucapan?',`<form class="server-form" id="greeting-form" data-result="${data.greeting}"><div class="greeting-placement"><img src="/api/v1/results/${data.greeting}/preview" alt="Foto dengan perkiraan letak ucapan"><span id="greeting-preview">${esc(result.greeting)}</span></div><p class="caption">Perkiraan letak ucapan; hasil tersimpan menggunakan huruf server. Ucapan lama diganti pada versi baru.</p><label>Ucapan<input class="input" name="text" maxlength="48" value="${esc(result.greeting)}" placeholder="Contoh: Selalu dekat di hati"></label><p class="caption"><span id="greeting-count">${result.greeting.length}</span>/48 karakter. Kosongkan kalau mau hapus ucapannya. Wajah tidak dibuat ulang; masa simpan hasil tidak diperpanjang.</p><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn primary" type="submit">Simpan versi baru</button></form>`); return;}
    if ('deleteProject' in data) {showDialog('Hapus proyek dan fotonya?',`<form class="server-form" id="delete-form" data-project="${data.deleteProject}"><p>Setelah kamu hapus, foto langsung tidak bisa diakses dan file masuk antrean penghapusan. Proyek dan fotonya tidak bisa dikembalikan.</p>${state.session.public_access?'':'<label>Kata sandi<input class="input" type="password" name="password" autocomplete="current-password" required></label>'}<label class="check"><input type="checkbox" name="confirm" required><span>Aku paham proyek dan fotonya akan dihapus dan tidak bisa dikembalikan.</span></label><p class="form-error" role="alert" tabindex="-1" hidden></p><button class="btn danger" type="submit">Hapus proyek</button></form>`); return;}
    if (!['generate','undo','feedback','selectResult','revokeGrant','reloadSupport','checkout','retryInit','reuseSource','generateSheet','reviewSheet','useSheet','faceFeedback','moreProjects','retryProject','retryConnection'].some(key=>key in data)) return;
    const initialRoute=route();
    state.busy=true; state.projectRead++; button.disabled=true;
    try {
      if ('moreProjects' in data) {const response=await api(`/api/v1/projects?offset=${state.nextOffset}`); state.projects.push(...response.items.filter(item=>!state.projects.some(existing=>existing.id===item.id))); state.nextOffset=response.next_offset; render({focus:false});}
      else if ('retryProject' in data) {state.projectErrors.delete(data.retryProject); await loadProject(data.retryProject);}
      else if ('retryConnection' in data) {await init();}
      else if ('generate' in data) await generate();
      else if ('generateSheet' in data) {
        const project=state.projects.find(item=>item.id===data.project);
        await api(`/api/v1/projects/${project.id}/character-sheets`,{method:'POST',headers:{'Idempotency-Key':requestKey('sheet',data.generateSheet,project.revision)},body:JSON.stringify({source_id:data.generateSheet,mode:'generated',expected_revision:project.revision})});
        state.keys.delete(`sheet:${data.generateSheet}:${project.revision}`);
        await refreshProjects(); closeDialog(); if(route()===initialRoute) render({focus:false}); schedulePoll(1000);
        toast('Referensi sedang disiapkan. Cek kemiripannya setelah selesai.');
      }
      else if ('reviewSheet' in data || 'useSheet' in data) {
        const project=state.projects.find(item=>item.id===data.project), sheet=project.character_sheets.find(item=>item.id===(data.reviewSheet || data.useSheet));
        let revision=project.revision;
        if ('reviewSheet' in data) {
          const response=await api(`/api/v1/character-sheets/${sheet.id}/review`,{method:'POST',body:JSON.stringify({decision:data.decision,expected_revision:revision})});
          revision=response.revision;
        }
        if ('useSheet' in data || data.decision==='approve') await api(`/api/v1/projects/${project.id}/slots/${data.slot}`,{method:'PUT',body:JSON.stringify({source_id:sheet.source_id,character_sheet_id:sheet.id,expected_revision:revision})});
        await refreshProjects(); closeDialog(); if(route()===initialRoute) render({focus:false});
        toast(data.decision==='reject'?'Referensi ditolak. Foto asli tetap bisa dipakai.':'Referensi karakter sudah dipasang.');
      }
      else if ('faceFeedback' in data) {
        const accepted=data.faceFeedback==='true', issue=accepted?'':data.faceFeedback==='wrong'?'wrong':'likeness';
        await api(`/api/v1/results/${data.result}/feedback`,{method:'POST',body:JSON.stringify({slot_id:data.slot,accepted,issue})});
        await refreshProjects(); closeDialog(); if(route()===initialRoute) render({focus:false});
        if (!accepted) {
          const project=state.projects.find(item=>item.results.some(result=>result.id===data.result)), result=project.results.find(item=>item.id===data.result), reference=result.references.find(item=>item.slot_id===data.slot);
          if (!correctionIssue(project,result)) correctionDialog(data.result,data.slot);
          else toast('Masukan tersimpan. '+correctionIssue(project,result));
        } else toast('Wajah sudah ditandai sesuai untuk versi ini.');
      }
      else if ('reuseSource' in data) {
        const updated=await api(`/api/v1/projects/${data.project}/slots/${data.slot}`,{method:'PUT',body:JSON.stringify({source_id:data.reuseSource,expected_revision:Number(data.revision)})});
        state.projects[state.projects.findIndex(item=>item.id===updated.id)]=updated;
        closeDialog(); if(route()===initialRoute) render(); toast('Fotonya sudah dipasang lagi!');
      }
      else if ('undo' in data) {const project=matchingProject(selected()); const updated=await api(`/api/v1/projects/${project.id}/undo`,{method:'POST',body:JSON.stringify({expected_revision:project.revision})}); state.projects[state.projects.findIndex(item=>item.id===project.id)]=updated; if(route()===initialRoute) render();}
      else if ('feedback' in data) {await api(`/api/v1/results/${data.result}/feedback`,{method:'POST',body:JSON.stringify({accepted:true})}); await refreshProjects(); if(route()===initialRoute) render({focus:false}); toast('Semua wajah ditandai sesuai untuk versi ini.');}
      else if ('selectResult' in data) {const project=state.projects.find(item=>item.results.some(result=>result.id===data.selectResult)); const updated=await api(`/api/v1/projects/${project.id}`,{method:'PATCH',body:JSON.stringify({selected_result_id:data.selectResult,expected_revision:project.revision})}); state.projects[state.projects.findIndex(item=>item.id===project.id)]=updated; if(route()===initialRoute) render({focus:false});}
      else if ('revokeGrant' in data) {await api(`/api/v1/support/grants/${data.revokeGrant}`,{method:'DELETE'}); await loadSupport(); toast('Akses staf ke fotomu sudah dicabut.');}
      else if ('reloadSupport' in data) await loadSupport();
      else if ('retryInit' in data) await init();
      else if ('checkout' in data && state.session.capabilities.payments_enabled) {const project=state.projects.find(item=>item.results.some(result=>result.id===data.checkout)); await api(`/api/v1/results/${data.checkout}/orders`,{method:'POST',headers:{'Idempotency-Key':requestKey('order',data.checkout,project.revision)},body:JSON.stringify({offer_id:project.offer_id})}); go('/orders');}
    } catch(error) {await showError(error,'reuseSource' in data ? $('#upload-form') : null);}
    finally {state.busy=false; if(button.isConnected) button.disabled=false;}
  });
  document.addEventListener('submit',async event=>{
    if (!event.target.matches('.server-form')) return;
    event.preventDefault();
    if (state.busy) return;
    const form=event.target, button=form.querySelector('[type="submit"]'), original=button.innerHTML, currentRoute=route();
    state.busy=true; state.projectRead++; button.disabled=true; button.textContent='Lagi menyimpan…'; form.setAttribute('aria-busy','true'); form.inert=true;
    const errorNode=form.querySelector('.form-error'); if(errorNode) errorNode.hidden=true; form.querySelectorAll('[aria-invalid]').forEach(input=>input.removeAttribute('aria-invalid'));
    try {
      if(form.id==='upload-form') {const file=form.elements.image.files[0]; if(file?.size>state.session.policy.upload_max_bytes) throw Error(`Foto melebihi ${Math.round(state.session.policy.upload_max_bytes/1048576)} MB. Pilih foto yang lebih kecil.`); await handleUpload(form);}
      else if(form.id==='batch-upload-form') await handleBatchUpload(form);
      else if(form.id==='template-change-form') await changeTemplate(form);
      else if(form.id==='correction-form') await correct(form);
      else if(form.id==='greeting-form') {const project=state.projects.find(item=>item.results.some(result=>result.id===form.dataset.result)); await api(`/api/v1/results/${form.dataset.result}/greetings`,{method:'POST',body:JSON.stringify({text:new FormData(form).get('text'),expected_revision:project.revision})}); await refreshProjects(); closeDialog(); if(route()===currentRoute) render({focus:false}); toast('Versi dengan ucapanmu sudah tersimpan!');}
      else if(form.id==='account-access-form') {const response=await api('/api/v1/support/account-access',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))}); form.reset(); const receipt=form.querySelector('.receipt'); receipt.textContent=response.message;receipt.hidden=false;}
      else if(form.dataset.replyTicket) {await api(`/api/v1/support/tickets/${form.dataset.replyTicket}/replies`,{method:'POST',body:JSON.stringify({message:new FormData(form).get('message')})}); await loadSupport(); toast('Jawaban tersimpan dalam pesan ini.');}
      else if(form.id==='support-form') {const fields=new FormData(form), payload=Object.fromEntries(fields); payload.image_access=fields.has('image_access'); if(payload.image_access&&!payload.project_id) throw Error('Pilih proyek dulu sebelum memberi staf akses ke fotonya, ya.'); await api('/api/v1/support/tickets',{method:'POST',body:JSON.stringify(payload)}); form.reset(); if(route()===currentRoute) await loadSupport(); toast('Pesanmu sudah terkirim. Cek balasannya di sini nanti, ya.');}
      else if(form.id==='delete-form') {const payload={confirmation:'DELETE'}; if(!state.session.public_access) payload.password=new FormData(form).get('password'); await api(`/api/v1/projects/${form.dataset.project}`,{method:'DELETE',body:JSON.stringify(payload)}); state.projects=state.projects.filter(item=>item.id!==form.dataset.project); await refreshProjects(); closeDialog(); if(route()===currentRoute) go('/projects'); toast('Proyek sudah dihapus dan nggak bisa dibuka lagi. Filenya sedang antre untuk dihapus.');}
    } catch(error) {await showError(error,form);}
    finally {state.busy=false; button.disabled=false; button.innerHTML=original; form.removeAttribute('aria-busy'); form.inert=false; if(errorNode && !errorNode.hidden) {const invalid=form.querySelector('[aria-invalid="true"]'); (invalid || errorNode).focus();}}
  });
  $('#dialog').addEventListener('close',()=>{releaseUploadPreviews(); if($('#batch-upload-form')) render({focus:false});});
  $('#dialog').addEventListener('cancel',event=>{if(state.busy) event.preventDefault();});
  window.addEventListener('hashchange',()=>{if($('#dialog').open&&!state.busy) closeDialog(); render();});
  function schedulePoll(delay=5000) {clearTimeout(state.pollTimer); state.pollTimer=setTimeout(poll,delay);}
  async function poll() {
    if (document.hidden || !state.session?.authenticated || state.busy || $('#dialog').open) {schedulePoll(); return;}
    if (state.projects.some(activeJob)) {
      try {
        const before=JSON.stringify(state.projects), initialRoute=route();
        const refreshed=await refreshProjects({background:true});
        if (refreshed && route()===initialRoute && !state.busy && !$('#dialog').open && before!==JSON.stringify(state.projects) && ['project','projects','studio'].includes(parts()[0])) {render({focus:false}); const project=state.projects.find(item=>parts().includes(item.id)); announce(project?`${projectTemplate(project).name}: ${labels[project.jobs[0]?.state] || 'Status diperbarui'}`:'Status Foto saya diperbarui.');}
      } catch(error) { state.connectionError='Status belum bisa diperbarui. '+error.message+' Jangan kirim proses baru sebelum statusnya jelas.'; $('#connection-message').textContent=state.connectionError; $('#connection-status').hidden=false; }
    }
    schedulePoll();
  }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden) schedulePoll(100);});
  async function init() {
    const fallback={authenticated:false,email_verified:false,public_access:false,capabilities:{payments_enabled:false},policy:{source_retention_days:Number(document.body.dataset.sourceRetention),result_retention_days:Number(document.body.dataset.resultRetention),upload_max_bytes:Number(document.body.dataset.uploadLimit)}};
    state.session ||= fallback;
    const sessionTask=api('/api/v1/session').then(session=>{state.session=session; state.publicErrors.delete('session'); render({focus:false});}).catch(error=>{state.publicErrors.set('session','Layanan akun belum bisa dihubungi. Panduan dan halaman publik tetap tersedia. '+error.message); render({focus:false});});
    const catalogTask=api('/api/v1/templates').then(catalog=>{state.templates=catalog.items;state.offers=catalog.offers;state.admission=catalog.admission_enabled;state.publicErrors.delete('catalog');render({focus:false});}).catch(error=>{state.publicErrors.set('catalog','Template belum bisa dimuat. '+error.message);render({focus:false});});
    render({focus:false});
    await Promise.all([sessionTask,catalogTask]);
    if (state.session.authenticated) {
      try {await refreshProjects();render({focus:false});} catch(error) {state.connectionError='Foto saya belum bisa dimuat. '+error.message;render({focus:false});}
    }
    schedulePoll();
  }
  init();
})();
