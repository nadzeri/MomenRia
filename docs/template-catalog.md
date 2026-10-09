# Event template catalog

MomenRia ships 28 templates: three original family scenes and 25 new event portraits. Templates support one to four people. The catalog can filter by occasion, person count, and university, and search names, clothing, campus names, and backgrounds.

## Load the collection

Run migrations before seeding:

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_catalog
```

The default seed creates drafts. Existing published versions, paused templates, face-slot identities, and active offers are preserved. For an isolated test environment, use `seed_catalog --test-publish`; this is rejected outside `APP_ENV=test`. Production publication still requires matching approved benchmark evidence. Generated previews do not establish likeness quality.

## Asset provenance

The 25 PNG originals in `static/app/assets/events/` were generated with the built-in image generation tool on 25 September 2026. All portrait subjects are fictional. Original PNGs preserve embedded provenance. WebP copies are display derivatives, downsampled to 960 × 720; originals remain unchanged for generation reference and checksum validation. Each preview's face count was checked with the project's face detector and its face centers recorded in `catalog/event_templates.json`, ordered from left to right.

University scenery is an AI illustration inspired by campus landmarks, not a photograph of the location or an official university template. Gowns and stoles are illustrative, with no claim of official faculty regalia. Landmark references are linked below; no university photographs were copied into these assets.

## Template inventory

| Template | Occasion | People | Campus background reference |
| --- | --- | ---: | --- |
| Natal di Rumah | Natal | 3 | — |
| Imlek Penuh Harapan | Imlek | 3 | — |
| Senja Ramadan | Ramadan | 2 | — |
| Idul Adha Bersama | Idul Adha | 4 | — |
| Galungan di Bali | Galungan | 2 | — |
| Waisak Penuh Damai | Waisak | 2 | — |
| Merah Putih Bersama | Hari Kemerdekaan | 4 | — |
| Cerita Tahun Baru | Tahun Baru | 2 | — |
| Ulang Tahun Si Kecil | Ulang Tahun | 3 | — |
| Sweet Seventeen | Ulang Tahun | 1 | — |
| Pre-wedding di Taman | Pre-wedding | 2 | — |
| Pre-wedding Jawa | Pre-wedding | 2 | — |
| Halo, Dunia | Bayi | 1 | — |
| Senyum Pertama | Bayi | 1 | — |
| Menanti Kehadiranmu | Maternity | 2 | — |
| Janji Seumur Hidup | Pernikahan | 2 | — |
| Bertumbuh Bersama | Anniversary | 2 | — |
| Wisuda UI | Wisuda | 1 | [Perpustakaan Crystal of Knowledge, Depok](https://simak.ui.ac.id/perpustakaan/) |
| Wisuda UGM | Wisuda | 1 | [Balairung, Bulaksumur](https://etd.repository.ugm.ac.id/penelitian/detail/205133) |
| Wisuda ITB | Wisuda | 1 | [Aula Barat, Kampus Ganesha](https://ditsp.itb.ac.id/bangunan/aula-barat/) |
| Wisuda IPB | Wisuda | 1 | [Grha Widya Wisuda, Dramaga](https://www.ipb.ac.id/news/index/2025/05/rektor-ipb-university-ajak-wisudawan-jadi-agen-perubahan-dan-pemimpin-masa-depan/) |
| Wisuda ITS | Wisuda | 1 | [Rektorat, Sukolilo](https://www.its.ac.id/uld/peta-aksesbilitas/sarana-prasarana-aksesbiltas-gedung-rektorat/) |
| Wisuda UNAIR | Wisuda | 1 | [Gedung bersejarah Kampus A, Surabaya](https://unair.ac.id/akses-pintu-masuk-fk-unair-dikembalikan-ke-era-peninggalan-belanda/) |
| Wisuda UNDIP | Wisuda | 1 | [Widya Puraya, Tembalang](https://mkep.fk.undip.ac.id/widya-puraya/) |
| Wisuda UNPAD | Wisuda | 1 | [Rektorat, Jatinangor](https://museum.unpad.ac.id/rektorat-2/rektorat-jatinangor/) |

## Generation prompts

Each original was generated with the following shared prefix followed by its `scene` from `catalog/event_templates.json` (except Natal, whose exact initial prompt is recorded below).

> Create one photorealistic premium portrait sample for MomenRia. Landscape 4:3 composition. Exactly the people described, all fictional Indonesians with natural skin texture, distinct faces clearly visible toward camera. Medium portrait, editorial photography, soft natural lighting. No additional people, no text, no logos, no watermark, no borders or collage. 

### imlek.png

Chinese New Year family: two Chinese Indonesian parents and their young son, scarlet festive shirts and dress, lanterns, plum blossoms, warm elegant interior, subtle gold accents.

### ramadan.png

Ramadan couple: adult man in cream baju koko and adult woman in modest cream dress and hijab seated in elegant courtyard with Islamic geometric arches, glowing fanous lanterns, late afternoon light.

### idul-adha.png

Eid al-Adha family portrait: father, mother wearing hijab, young boy and young girl. White and olive modest festive clothes, garden courtyard with elegant Islamic-inspired arches, morning light, no animals.

### galungan.png

Galungan Balinese adult couple, woman in modest ivory kebaya and gold sash, man in white shirt and udeng headdress, carved Balinese courtyard gate, decorative penjor bamboo poles arching in background.

### waisak.png

Vesak Indonesian adult couple in simple white long-sleeve outfits, serene garden with distant Borobudur-inspired stone stupas and warm lantern decor, golden dawn. Faces frontal, no worship gestures.

### kemerdekaan.png

Indonesian Independence Day family: father, mother, son and daughter in coordinated red and white casual clothes; tidy garden with Indonesian red-over-white flag bunting, bright cheerful morning.

### tahun-baru.png

New Year celebration adult couple in elegant navy evening clothes, gold string lights and distant fireworks viewed from terrace, soft flattering warm light on faces, sophisticated festive atmosphere.

### ulang-tahun-anak.png

Birthday party family of THREE: five-year-old child centered with mother and father, pastel mint peach balloon arch, simple birthday cake on table, parents' faces separate and clearly visible, bright joyful natural light.

### sweet-seventeen.png

Solo Indonesian girl celebrating her seventeenth birthday, modest pastel lilac party dress, small cake and lilac balloon arrangement, warm cream studio, tasteful age-appropriate portrait, joyful smile.

### prewedding-taman.png

Pre-wedding adult Indonesian couple standing in green botanical garden, ivory modest flowing dress and beige suit, both faces turned toward camera, light floral bouquet, romantic late-afternoon sun.

### prewedding-jawa.png

Pre-wedding adult Javanese Indonesian couple, woman in ivory kebaya with batik skirt, man in dark beskap jacket batik cloth and blangkon, elegant timber joglo pendopo, both face camera.

### bayi-baru-lahir.png

Exactly ONE newborn Indonesian baby sleeping safely on back on flat cream blanket, safely swaddled in cream cotton, face fully unobstructed, overhead portrait, soft studio window light, no props near face, no adults.

### bayi-enam-bulan.png

Exactly ONE six-month-old Indonesian baby lying safely on back on flat warm oatmeal blanket looking at overhead camera smiling, fully clothed in soft sage knitted romper, no adults, no obstructing props, bright soft natural light.

### maternity.png

Maternity portrait of adult pregnant Indonesian woman in modest flowing cream maternity dress and adult male partner in linen cream shirt, standing side by side touching hands over bump, both faces frontal, warm minimalist studio with gauze curtains.

### pernikahan.png

Indonesian wedding adult bride and groom, ivory bridal kebaya modest dress and white beskap, jasmine hair ornament, refined ivory floral pelaminan backdrop, both looking toward camera, medium portrait.

### anniversary.png

Anniversary portrait of middle-aged Indonesian married couple, woman in terracotta modest dress, man in brown linen blazer, small white floral arrangement, warm elegant wood-paneled studio, relaxed affection, both facing camera.

### wisuda-ui.png

Solo young adult Indonesian woman graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, faceted stone-and-glass library building with grass-covered sloping roof beside campus lake visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-ugm.png

Solo young adult Indonesian man graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, white Balairung main building in Bulaksumur with broad columned portico and terracotta tiled roof visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-itb.png

Solo young adult Indonesian woman graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, Aula Barat heritage building, steep distinctive layered dark curved traditional roof, stone base and tropical trees visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-ipb.png

Solo young adult Indonesian man graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, Grha Widya Wisuda auditorium in Dramaga, broad pitched reddish-brown roof, open columned entrance, lush Bogor trees visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-its.png

Solo young adult Indonesian woman graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, three-storey ITS rectorate building in Sukolilo with terracotta pitched roof, light facade, formal landscaped lawn visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-unair.png

Solo young adult Indonesian man graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, historic white colonial medical faculty building at Campus A, terracotta roof and rows of columns, tropical gardens visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-undip.png

Solo young adult Indonesian woman graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, Widya Puraya main building in Tembalang, grand white facade with large central traditional tiered terracotta roof, landscaped lawn visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### wisuda-unpad.png

Solo young adult Indonesian man graduate in plain black academic gown, mortarboard and neutral cream stole, holding simple diploma tube without text. Subject in foreground to right of center, waist-up portrait, distinctive circular rectorate building in Jatinangor with white columns and broad terracotta conical roof, green lawn visible as campus-inspired background. Broad enough framing to see building, soft morning light. Architecture is an illustrative interpretation, no university logos or official insignia.

### natal.png

Create one photorealistic premium Indonesian family portrait sample for MomenRia photo templates. Landscape 4:3 composition, 1536x1152. Christmas at home in Indonesia: exactly THREE fictional Indonesian people, adult father on left, adult mother on right and eight-year-old daughter centered slightly forward, all faces clearly visible looking toward camera. Warm cream living room, decorated Christmas tree, understated red and forest-green knit outfits, soft window light, elegant editorial family photography, natural skin texture, relaxed smiles. Waist-up medium portrait, clean separation between faces. No other people, no text, logos, watermarks, collage or UI. Full bleed photograph.

