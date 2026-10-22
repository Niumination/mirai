# Audit non-teknis — kenapa localhost belum terasa “ekosistemmu”

Tanggal baca: 13 Oktober 2026. Sumber: repo `main` `051843b`, aturan adopsi yang kamu kunci, dan apa yang Hermes Mac sudah buktikan hidup.

Ini **bukan** daftar bug untuk diklik. Ini peta: apa yang kamu lihat, apa yang sebenarnya bekerja, dan ke mana kita lanjut.

---

## Satu kalimat

Yang terbuka di localhost **bukan markas Niumination**. Itu **jendela pengamat** yang kami pasang di samping mesin yang sudah kamu punya (Hermes + Telegram + wiki). Jendela itu sudah hidup dan lulus tes Mac — tapi isinya masih **membaca mesin generik**, belum **menceritakan ekosistemmu**.

Karena itu wajahnya bisa “berjalan” (ping hijau, 10 foto kru, 22 tes lulus) sementara perasaanmu benar: *ini belum seperti yang kita kerjakan*.

---

## Analogi rumah

Bayangkan tiga ruangan:

1. **Dapur & orang yang memasak** — Hermes di Mac, grup Telegram 10 topik, skill, cron wiki, gateway. Ini ekosistem aktual. Kita **dilarang merombak** sebagian besarnya (jangan ganti gateway, jangan pasang 3 “persona pabrik”, jangan hidupkan plugin Telegram paket ini).
2. **Buku resep & peta** — folder `docs/`, aturan topik, larangan adopsi. Ini tempat niatmu tertulis paling jernih.
3. **Jendela kaca di dinding** — Mission Control di port 8800 (localhost). Dia **melihat ke dalam rumah**, tidak menjadi rumah.

Kita sudah menggosok kaca (konsol MIRAI, avatar robot, installer Mac, tes). Orang di dapur tidak berubah. Buku resep belum jadi denah yang jendela itu pakai.

Kalau kamu berdiri di jendela dan berharap melihat kota Agent seperti video referensi, atau 10 peran Telegram yang sudah kamu setujui — wajar kecewa. Jendela itu masih menggambar **denah rumah lain** (paket MIRAI generik: Executor + Researcher + Writer + Developer, misi, kota datar, chat lokal).

---

## Apa yang sebenarnya hidup di Mac (fakta, bukan harapan)

Dari laporan Hermes dan aturan yang kamu kunci:

- Satu otak Hermes (**satu profil default**), bukan 10 “karyawan” terpisah di folder profil.
- **Sepuluh topik Telegram** di satu grup forum — itu pembagian kerja yang nyata. Router yang menang = `config.yaml` Hermes, **bukan** plugin MIRAI (plugin sengaja OFF).
- Wiki di Desktop Niumination, cron malam **lima** pekerjaan (bukan tujuh; mail dan cadangan luar **jangan**).
- Mission Control **com.mirai.** di :8800 — hidup, ping oke, health oke setelah perbaikan import avatar.
- niu-mission-control lama **diarsipkan**; jangan hidupkan lagi di :5200.
- Gateway, 9router, A2A **milik Hermes** — off-limits. Dashboard tidak boleh berpura-pura mengendalikannya.
- Cockpit / papan misi **kosong** bukan karena rusak: belum ada kartu kerja. Aturanmu: jangan isi palsu.

Jadi “11 agen, 10 pakai foto” di API artinya: jendela **berhasil menempelkan wajah** pada kode dua huruf. Itu **bukan** bukti bahwa sepuluh topik Telegram, wiki, dan cron sudah jadi satu layar yang kamu maksud.

---

## Kenapa tampilan tidak cocok dengan kerja kita

### 1. Kita menaruh wajah di manekin yang salah ukuran

Sepuluh bust robot (TR, RS, BD, …) dipasang ke **kode persona di konsol**. Kerja kita yang kamu setujui soal **fungsi topik** adalah id Telegram: 1 inbox, 13902 bos, 7402 bak pasir, 803 vs 804, 1172 vs 12707, 8853 dinas, 12595 noise cron.

Konsol tidak dibangun sebagai “peta 10 topik itu”. Dia dibangun sebagai “daftar agen Hermes + kartu mosaic + chat ke proses lokal”. Foto menempel di manekin paket, bukan di kursi rapat grupmu.

### 2. Dua cerita produk dalam satu nama “MIRAI”

Di README dan arsitektur masih ada cerita **paket siap-deploy 3 lapis**:

- wiki gaya Agent OS,
- **armada 3 spesialis + Executor** (itu yang kamu **larang** dipasang),
- konsol 15 halaman (cockpit, kota, misi, tangan, suara, terminal, …).

Cerita **Niumination** yang kita kunci:

- jangan create-fleet,
- jangan 3 SOUL pabrik,
- `config.yaml` menang,
- plugin OFF,
- 10 topik dengan fungsi yang tidak boleh dicuri satu sama lain,
- UI hemat, tinta/krim/bara, tanpa CDN,
- jujur kalau kosong.

Localhost mengikuti cerita **paket**. Perasaanmu mengikuti cerita **Niumination**. Keduanya sah — belum dijadikan satu produk.

### 3. “Lulus tes” ≠ “sesuai keinginan”

Tes Mac membuktikan: layanan tidak rubuh, rute foto tidak bocor, installer tidak merusak gateway. Tes **tidak** bertanya: apakah layar ini menampilkan 10 fungsi topik? apakah wiki yang terbuka adalah wiki Desktop-mu? apakah chat di halaman = percakapan grup? apakah kota 3D? apakah cockpit merangkum kerja nyata hari ini?

Semua jawaban itu saat ini: **belum, dan sebagian memang sengaja belum**.

### 4. Jendela hampir hanya membaca — dapur menulis di tempat lain

Percakapan hidup di Telegram. Ingatan panjang di wiki. Jadwal di cron Hermes. Model lewat 9router / huancheng.

Halaman localhost punya **chat sendiri**, **misi sendiri**, **basis data sendiri**. Kalau dapur sepi di papan misi, jendela jujur kosong. Kalau dapur ramai di Telegram, jendela **bisa tetap sepi**, karena plugin pemetaan topik tidak dihidupkan dan konsol tidak menelan riwayat grup.

Itu celah terbesar antara “ekosistem aktual” dan “yang kulihat di browser”.

### 5. Ada dua dashboard dalam kepala proyek

- Konsol MIRAI satu file (yang kita rapikan + avatar) — ini yang :8800 layani.
- “Halaman desain” lama (~9 MB, kota 3D, tangan, three.js) — **tidak dikirim sebagai kode**; README bilang taruh file unduhan sendiri.

Referensi YouTube (bust 3D, kota agen) dekat dengan **halaman desain**, bukan dengan konsol datar yang sekarang. Kita sudah menolak meniru kota neon, lalu memasang bust di **kartu datar**. Hasilnya: bukan identicon, tapi juga bukan markas yang kamu bayangkan.

### 6. Angka di layar mudah menyesatkan

- **11 agen** ≈ 1 profil Hermes + 10 baris topik/peta — bukan 11 orang di kantor.
- **54 rute, 15 halaman** = kelengkapan *konsol paket*, termasuk hal yang bukan prioritasmu (deploy agen pabrik, terminal, hand mode, voice).
- **Wiki di dokumen** sering tertulis `~/wiki`; **keputusanmu** folder Desktop Niumination. Kalau jendela masih mencari jalur paket, memori yang kamu pakai tidak muncul.

### 7. Bahasa dan branding

Kamu minta UI Indonesia dulu, sakelar Inggris. Konsol paket masih banyak copy Inggris operasional (“Working”, “Talk to an agent”, lede panjang). Branding MIRAI sudah nama — rasa “milik Niumination / kerja dinas + kru AI” belum jadi bahasa layar.

---

## Apa yang *sudah* sesuai niat (supaya tidak dibongkar)

Jangan dianggap gagal total. Ini yang sudah benar dan harus dijaga:

- Mac, bukan Linux sebagai sasaran.
- Nama MIRAI; niu-mc lama tidak dihidupkan.
- Skill bank Hermes tidak diacak dari Arena.
- Plugin Telegram paket **mati**; yaml tidak ditulis massal.
- Tidak memasang 3 karyawan pabrik.
- Cockpit boleh kosong.
- Avatar: arah humanoid berpakaian, gelap — sudah di kabel, hidup di Mac.
- Paket ramping di workspace Arena (binary tangan tidak dipaksa masuk zip).
- Satu perbaikan nyata: tanpa `import avatars`, seluruh daftar agen dan health rubuh — itu bug jendela, sudah ditutup.

---

## Arah yang masuk akal (pilih satu poros, baru kita kerjakan)

Kita tidak bisa “lanjutkan semua halaman” dan berharap terasa utuh. Perlu **satu janji layar**.

### Poros A — Jendela jujur untuk *rumah yang ada*

Localhost = **status Niumination**, bukan demo MIRAI generik.

Layar utama: 10 kursi topik (fungsi yang kamu kunci), apakah cron lima hidup, apakah wiki Desktop ada detak, gateway hanya “hidup/mati” tanpa tombol bahaya, chat **bukan** saingan Telegram.

Hapus atau sembunyikan dari menu: Deploy agen pabrik, Kota hias, Hand, mungkin Terminal/Voice — sampai kamu minta.

**Cocok jika:** kamu ingin membuka laptop dan *mengenali kerja hari ini*.

### Poros B — Markas visual (bust + ruang), tetap datar dulu

Pertahankan mosaic dan foto. Tiap ubin = satu fungsi topik, bukan kode acak. Kota = peta 10 bangunan bernama sesuai TOPIK, bukan “Cabin” generik.

**Cocok jika:** yang mengganggumu adalah *wajah dan tata ruang*, bukan kurangnya data Telegram.

### Poros C — Satu saluran kerja (wiki + inbox)

Fokus: General (1) menampung manusia, Orkestrator (13902) memecah kerja, hasil masuk wiki, konsol hanya menampilkan **berkas dan antrian** itu.

**Cocok jika:** yang mengganggumu adalah *tidak ada jejak kerja*, bukan kurangnya animasi.

Tidak disarankan sekarang: menghidupkan plugin Telegram, create-fleet, meniru kota neon video, mengisi misi palsu, menyentuh gateway. Itu akan membuat localhost “ramai” dengan cara yang kamu sudah tolak.

---

## Giliran ini selesai di mana

Audit: **jendela hidup, cerita produk belum satu, data dapur belum jadi isi jendela.**

Giliran berikutnya baru berarti jika kamu pilih poros A, B, atau C (atau gabungan sempit, misalnya A+B: status 10 topik + wajah, tanpa halaman pabrik).

Sampai pilihan itu ada, menambah fitur di 15 halaman hanya akan membuat localhost **lebih lengkap sebagai paket MIRAI** dan **lebih jauh dari ekosistem yang kamu maksud**.
