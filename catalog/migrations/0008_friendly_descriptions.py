from django.db import migrations


DESCRIPTIONS = (
    ('studio', 'Sederhana, hangat, dan tak lekang waktu.', 'Foto bareng yang simpel dan hangat. Cocok dipajang di rumah.'),
    ('home', 'Dekat di hati. Nyaman seperti di rumah.', 'Santai di rumah, dekat sama orang tersayang.'),
    ('lebaran', 'Rayakan hari baik dengan orang tersayang.', 'Lebaran makin lengkap dengan foto bareng orang tersayang.'),
    ('natal', 'Hangatnya Natal bersama keluarga di dekat pohon yang berkilau.', 'Natal di rumah, bareng orang tersayang dan pohon yang berkilau.'),
    ('imlek', 'Sambut tahun yang baru dengan kehangatan keluarga dan lentera merah.', 'Tahun baru, harapan baru. Yuk, foto bareng di bawah lentera merah.'),
    ('ramadan', 'Kenang kebersamaan di bulan Ramadan dalam cahaya senja yang lembut.', 'Senja Ramadan paling enak dinikmati bareng. Simpan momennya di sini.'),
    ('idul-adha', 'Hari raya yang hangat untuk seluruh keluarga dengan latar halaman rumah.', 'Kumpul di halaman rumah saat Idul Adha. Yuk, foto bareng keluarga.'),
    ('galungan', 'Kebersamaan hari Galungan dengan nuansa halaman Bali dan penjor.', 'Hari Galungan, halaman Bali, dan penjor. Lengkap buat foto bareng.'),
    ('waisak', 'Simpan kebersamaan dalam suasana Waisak yang tenang dan hangat.', 'Suasana Waisak yang tenang buat momen hangat bersama orang tersayang.'),
    ('kemerdekaan', 'Rayakan 17 Agustus dengan senyum keluarga dan semangat merah putih.', 'Merah putih, senyum lebar. Yuk, rayakan 17 Agustus bareng keluarga!'),
    ('tahun-baru', 'Awali cerita baru dengan potret berdua bernuansa perayaan malam.', 'Tahun baru, foto baru. Mulai cerita berikutnya berdua, yuk.'),
    ('ulang-tahun-anak', 'Tawa si kecil, balon pastel, dan pelukan orang tua di hari spesial.', 'Ada balon, ada pelukan, ada si kecil yang tambah besar. Selamat ulang tahun!'),
    ('sweet-seventeen', 'Potret ulang tahun ke-17 dengan bunga, kue, dan nuansa pastel.', 'Akhirnya 17! Rayakan dengan bunga, kue, dan warna pastel favoritmu.'),
    ('prewedding-taman', 'Simpan awal cerita berdua di taman hijau dengan cahaya sore.', 'Sebelum hari besar, foto berdua dulu di taman dengan cahaya sore.'),
    ('prewedding-jawa', 'Potret berdua dengan sentuhan kebaya, beskap, dan pendopo Jawa.', 'Kebaya, beskap, dan pendopo Jawa. Pas buat cerita kalian berdua.'),
    ('bayi-baru-lahir', 'Potret bayi baru lahir yang lembut dalam balutan warna krem.', 'Halo, si kecil! Simpan momen awalnya dengan bedong krem yang lembut.'),
    ('bayi-enam-bulan', 'Rayakan tumbuh kembang si kecil dengan potret ceria bernuansa hangat.', 'Si kecil makin besar, senyumnya makin banyak. Yuk, simpan momen ini.'),
    ('maternity', 'Kenang masa menanti buah hati dalam potret berdua yang hangat.', 'Sambil menunggu si kecil, simpan dulu momen hangat kalian berdua.'),
    ('pernikahan', 'Abadikan hari pernikahan dalam suasana pelaminan yang elegan.', 'Hari bahagia kalian, dengan latar pelaminan yang manis buat dikenang.'),
    ('anniversary', 'Rayakan tahun-tahun kebersamaan dengan potret yang tak lekang waktu.', 'Sudah sejauh ini bareng. Yuk, rayakan dengan foto berdua lagi.'),
    ('wisuda-ui', 'Rayakan kelulusan Universitas Indonesia dengan ilustrasi latar Perpustakaan Crystal of Knowledge, Depok.', 'Akhirnya lulus UI! Foto dengan ilustrasi Perpustakaan Crystal of Knowledge, Depok, yuk.'),
    ('wisuda-ugm', 'Rayakan kelulusan Universitas Gadjah Mada dengan ilustrasi latar Balairung, Bulaksumur.', 'Akhirnya lulus UGM! Simpan momen banggamu dengan ilustrasi Balairung, Bulaksumur.'),
    ('wisuda-itb', 'Rayakan kelulusan Institut Teknologi Bandung dengan ilustrasi latar Aula Barat, Kampus Ganesha.', 'Lulus ITB, saatnya foto! Pilih latar ilustrasi Aula Barat, Kampus Ganesha.'),
    ('wisuda-ipb', 'Rayakan kelulusan IPB University dengan ilustrasi latar Grha Widya Wisuda, Dramaga.', 'Lulus IPB, senyum dulu! Ada ilustrasi Grha Widya Wisuda, Dramaga, buat latarmu.'),
    ('wisuda-its', 'Rayakan kelulusan Institut Teknologi Sepuluh Nopember dengan ilustrasi latar Rektorat, Sukolilo.', 'Akhirnya lulus ITS! Rayakan dengan foto berlatar ilustrasi Rektorat, Sukolilo.'),
    ('wisuda-unair', 'Rayakan kelulusan Universitas Airlangga dengan ilustrasi latar Gedung bersejarah Kampus A, Surabaya.', 'Lulus UNAIR, waktunya rayakan! Foto dengan ilustrasi gedung bersejarah Kampus A, Surabaya.'),
    ('wisuda-undip', 'Rayakan kelulusan Universitas Diponegoro dengan ilustrasi latar Widya Puraya, Tembalang.', 'Akhirnya lulus UNDIP! Simpan momenmu dengan ilustrasi Widya Puraya, Tembalang.'),
    ('wisuda-unpad', 'Rayakan kelulusan Universitas Padjadjaran dengan ilustrasi latar Rektorat, Jatinangor.', 'Lulus UNPAD, foto dulu! Ada ilustrasi Rektorat, Jatinangor, buat momen banggamu.'),
)


def update_descriptions(apps, schema_editor):
    templates = apps.get_model("catalog", "TemplateVersion").objects.using(schema_editor.connection.alias)
    for slug, old, new in DESCRIPTIONS:
        templates.filter(slug=slug, version=1, description=old).update(description=new)


def restore_descriptions(apps, schema_editor):
    templates = apps.get_model("catalog", "TemplateVersion").objects.using(schema_editor.connection.alias)
    for slug, old, new in DESCRIPTIONS:
        templates.filter(slug=slug, version=1, description=new).update(description=old)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_solo_portraits")]
    operations = [migrations.RunPython(update_descriptions, restore_descriptions)]
