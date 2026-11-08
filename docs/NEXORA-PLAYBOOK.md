# Playbook: MIRAI menyerupai & melebihi NEXORA — tanpa jadi NEXORA

Tanggal: 2026-11-08.  
Video: [Ytpp65paFpY](https://www.youtube.com/watch?v=Ytpp65paFpY) (28:11).  
Prompt: Drive `NEXORA-Prompts-Fresh-Hermes-KomputerMechanic.md` (46).  
Dapur: [ecosystem-config](https://github.com/niumination/ecosystem-config) `AGENTS.md` (9 larangan).  
Jendela: [mirai](https://github.com/Niumination/mirai) + workspace Arena.

**Melebihi** ≠ lebih gimmick. Melebihi = lebih **benar untuk rumah ini**, lebih **cepat**, lebih **jujur**, lebih **aman**, lebih **bisa dipakai setiap hari**.

---

## 0. Keputusan yang tidak dinegosiasi

Dari video kita **ambil rasa** (satu markas, wajah kru, status kerja, dokumen, jadwal, mesin).  
Dari Niumination kita **ambil hukum**:

1. Satu otak Hermes. Bukan 16 profil. Bukan create-fleet / hiring UI.
2. Sepuluh kursi = thread Telegram tetap (lihat tabel). Plugin OFF. `config.yaml` manusia.
3. Wiki (kode `roster._wiki_dir`): `CREW_WIKI_DIR` jika set → else `$HOME/Desktop/Niumination/wiki` jika folder ada → else `~/wiki`. Sumber kebenaran hidup = Desktop. Bukan `~/mirai/data/docs`.
4. Cron malam **lima**. Jangan mail-sweep / offsite.
5. Gateway, 9router, A2A, SOUL: lampu, bukan kemudi.
6. Bind 127.0.0.1. State `~/mirai/data`. Jangan 0.0.0.0.
7. UI self-contained, tanpa CDN, ink/krim/bara, ID default.
8. Cockpit **kosong jujur**. Jangan 142 misi palsu.
9. `AGENTS.md` ekosistem: **satu perubahan per sesi** di dapur; jendela boleh banyak file asal satu *janji layar*.
10. Skill bank 238: jangan salin ke Arena / Hermes dari sini.

Anti-tujuan (ada di video, **dilarang** di MIRAI): Hand+MediaPipe, game balap, napas 4-7-8, ElevenLabs, cincin 3D Three.js 9 MB, tombol hire/fire, chat saingan 10 topik Telegram, seed misi teatrikal.

---

## 1. Sepuluh kursi (satu-satunya “fleet”)

Grup `Niu-MissionControl` `chat_id: -1004204696417`.

| Kode | Thread | Nama | Kerja | Bukan |
|------|--------|------|--------|--------|
| TR | 1 | General | Inbox, arahkan | Bukan bos |
| RS | 802 | Research | Cari, kutip, wiki research | Bukan Builder |
| BD | 803 | Builder | Kode / satu PR | Bukan QA akhir |
| QA | 804 | QA | Lolos/tidak | Bukan nulis fitur |
| KR | 1172 | Kreator | Brand, humanizer | Bukan kurikulum |
| SB | 7402 | Serbaguna | Sandbox | Bukan bak sampah |
| AS | 8853 | ASN | SKP dinas, huancheng | Bukan edu umum |
| CR | 12595 | Cron | Laporan job | Bukan minta skrip |
| ED | 12707 | Edu | Kurikulum | Bukan brand |
| OR | 13902 | Orkestrator | Satu-satunya bos | Bukan basa-basi |

Tautan dalam (rumus Hermes/Telegram): `https://t.me/c/4204696417/<thread_id>` — angka `t.me/c/` = chat_id tanpa awalan `-100`. [2](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/telegram.md)  
`topics.json` **tidak** memetakan id `1` (inbox = agent utama). Tautan `.../1` tetap sah sebagai topik General. Jendela **tidak** mengirim pesan.

---

## 2. Video → layar MIRAI (melebihi)

| Bab video | NEXORA | MIRAI (target) | Melebihi karena |
|-----------|--------|----------------|-----------------|
| 0:00 cincin 3D + tangan | 16 bust, pinch | **Kota CSS 10 gedung** + keyboard; still WebP jika `prefers-reduced-motion` | A11y, 0 CDN, 0 kamera |
| 2:20 cockpit cluster | success %, 142 misi | Cluster **nyata**: 10 kursi, 5 cron hidup/mati, wiki mtime, gateway lampu | Tidak bohong |
| Tambah agen | hiring | **Tidak ada.** 10 kursi terkunci | Integritas tupoksi |
| 6:23 voice | Piper/EL | Opsional belakangan; default **mati** | Privasi, no spend |
| 8:38 hand + game | MediaPipe 30 MB | **Tidak** | Berat, off-limits zip |
| 11:56 chat | 16 profil Hermes | Tombol **buka topik Telegram**; chat localhost hanya profil `default` jika ada, label jujur “bukan grup” | Dapur = Telegram |
| 12:31 missions | Executor pilih tim | **Kanban Hermes** jika ada baris; jika 0 → kosong. Rencana kerja = **OR**, bukan UI hire | Sesuai 13902 |
| 17:51 docs | `~/nexora` reports | **Wiki Desktop** (index, log, processed/) | Memori yang Anda pakai |
| 18:30 schedule | cron agen buat sendiri | **5 job** + heartbeat; tidak create dari UI kecuali sudah ada API read | Tidak spawn cron liar |
| 19:17 city biru/oranye | gedung 16 | 10 mosaik/gedung: working / ready / unknown dari house+roster | Nama tupoksi kebaca 160px |
| 21:03 health | CPU RAM disk | Sudah `health.py` Darwin | Pertahankan |
| 21:35 files | edit SOUL | Baca SOUL; **tulis hanya** file yang ADOPT izinkan + backup | Hukum dapur |
| 22:06 terminal | pty | **Sembunyi** sampai diminta | Risiko |
| 23:37 settings | tema bebas | Ink/krim/bara **kunci**; ID/EN; reduced-motion | Merek |

Cari di header (video 2:20): cari **kode / nama kursi / thread**, bukan 16 profil.

---

## 3. Arsitektur informasi (janji layar)

**Nav terlihat:** Status (cockpit=house), 10 kursi, Jadwal, Kesehatan, Berkas (read), Pengaturan.  
**Nav tersembunyi (kode tetap, `hidden`):** deploy, city-3D lama, missions-teater, docs-paket, terminal, voice, hand.  
**City baru** = permukaan **Status** atau ganti `city` yang sekarang hidden: isometric CSS, bukan Three.

API yang boleh diandalkan (sudah ada): `/api/house`, `/api/agents`, `/api/cron`, `/api/health`, `/api/ping`, `/api/avatars/pack`, `?still=1`.

API yang **jangan** jadi pintu depan: `/api/workforce/*`, `/api/missions` (kecuali baca kosong), `/api/voice/*`, `/api/terminal/*`.

Wiki: tambah **pembaca** path Desktop (env `MIRAI_WIKI` / sudah di settings) — jangan meniru `~/mirai/data/docs` sebagai “Docs tab” utama.

---

## 4. Visual “melebihi kota 3D”

- Satu file HTML, CSS dari-nol (Operate), tanpa CDN. [3](https://reintech.io/blog/creating-responsive-dashboard-with-css)
- 10 kartu/gedung: `button`, urutan DOM = urutan keyboard. Gerak = transform; `prefers-reduced-motion` = still WebP. [2](https://medium.com/@francesco-saviano/building-a-drag-to-reorder-dashboard-with-css-grid-pointer-events-and-flip-70dd214bf5bf)
- Pulsa **bara** hanya jika status working; ready = krim; unknown = ink. Bukan biru/oranye NEXORA.
- Avatar pack WebP animasi yang sudah ada.
- Fokus terlihat, skip link, `aria-live` untuk toast (upstream Nov 7 sudah mulai).

Tidak: Three.js, game, cincin pinch.

---

## 5. Lantai teknis yang sudah cukup (jangan dibangun ulang)

Router Python stdlib, SQLite WAL, LaunchAgent `com.mirai.*`, gate token, Host allowlist, health Darwin, roster 10 kode, house 10 thread, avatar WebP+still, i18n kerangka, tes `prove.sh` / `mac-verify.sh`.

Yang **kode paket NEXORA sudah ada tapi salah janji:** workforce, missions teater, voice, hand, 15 surface di README. Playbook ini **menyembunyikan**, bukan menghapus tes.

---

## 6. Fase terapan (satu janji per fase)

Urutan wajib. Jangan loncat ke tangan/kota 3D.

| Fase | Janji | Bukti selesai | Bukan |
|------|--------|----------------|--------|
| **F0** | Konteks terkunci (dokumen ini + NEXORA-NIUMINATION) | Pemilik setuju anti-tujuan | Kode UI |
| **F1** | Nav = Poros A; Status = 10 kursi house + cluster jujur | **Arena 2026-11-08:** chat+integrasi `hidden`; mosaik = tautan Telegram; `telegram_url` di house | Three.js |
| **F2** | Kota CSS 10 gedung (atau mosaic diperkaya) + tautan Telegram | **Arena:** mosaik 5×2, OR lebih tinggi; tautan Telegram F1 | Profil baru |
| **F3** | Jadwal = 5 cron nyata; Docs = wiki Desktop (baca) | **Arena:** nav Wiki; `GET /api/wiki` + `/page` baca-saja `roster._wiki_dir()` | Tulis wiki dari UI tanpa verb |
| **F4** | Cari kursi; i18n sisa copy layar Status/Jadwal | **Arena:** kunci page/lede jadwal, kesehatan, berkas, pengaturan | Copy CLI jadi Indonesia |
| **F5** | README/ARSITEKTUR tidak mengiklankan fleet 3 orang | **Arena:** README Poros A; `00-ARSITEKTUR` diberi peringatan paket | create-fleet.sh tetap di tree sebagai **artefak terlarang** |
| **F6** | Mac: reload **hanya** `com.mirai.mission-control` | **Arena tidak mengerjakan.** Lihat `docs/HANDOFF-MAC.md` | install-habits |

Melebihi video di F1–F4 sudah cukup untuk “sehari-hari”. F6 = terapan sempurna di mesin.

---

## 7. Daftar kebutuhan (bukan unduhan 9 MB)

- [x] 10 WebP + still + `pack_for`
- [x] `/api/house`
- [x] Palet ink/krim/bara
- [ ] Renderer Status memakai **hanya** house (bukan mosaic agen pabrik)
- [ ] CSS kota/grid 10
- [ ] Deep link Telegram 10
- [ ] Env/path wiki Desktop di settings + halaman baca
- [ ] Cluster: cron×5, wiki mtime, gateway bool
- [ ] Copy i18n Status/Jadwal
- [ ] README Poros A
- [ ] Uji: keyboard 10 gedung, reduced-motion, house 10, pack webp, tanpa workforce di nav

Tidak perlu: MediaPipe, Three, 16 wajah, game, EL key.

---

## 8. Risiko jika “menerapkan video sempurna”

| Jika | Akibat |
|------|--------|
| Hire seperti menit 2:20 | Melanggar 1 profil + freeze proyek |
| Chat localhost = grup | Dua dapur, riwayat pecah |
| Kota Three.js | CDN/berat, preview Arena rusak, a11y jatuh |
| Docs = `data/docs` | Wiki Desktop tidak kelihatan (celah audit lama) |
| README tetap 15 surface | Orang (termasuk agen) salah pasang fleet |

---

## 9. Kriteria “sempurna” (penerimaan pemilik)

1. Buka `:8800` → mengenali **10 fungsi topik**, bukan Executor/Writer/Dev.
2. Klik kursi → Telegram topik yang benar **atau** kartu tupoksi; tidak membuat profil.
3. Jadwal menunjukkan **5** cron wiki / jujur jika mati.
4. Wiki yang terbuka = folder Desktop.
5. Tidak ada tombol yang menulis `config.yaml`, SOUL, gateway, 9router.
6. Kosong = kosong. Avatar bernapas kecuali reduced-motion.
7. Lebih ringan dari video (tanpa 9 MB, tanpa 30 MB tangan).
8. Bahasa ID, merek MIRAI, bukan NEXORA.

Kalau 1–8 benar, MIRAI **melebihi** NEXORA untuk *rumah ini*, meski tidak punya pinch dan 16 gedung.
