# NEXORA (video) → MIRAI / Niumination

Sumber video: [Komputer Mechanic — Mission Control 3.0](https://www.youtube.com/watch?v=Ytpp65paFpY) (28:11, 28 Sep 2026). Transkrip + deskripsi + 46 prompt Drive. Ekosistem aktual: [niumination/ecosystem-config](https://github.com/niumination/ecosystem-config) `9181f5b`. MIRAI upstream: [Niumination/mirai](https://github.com/Niumination/mirai) `eef554b`.

Bukan klon 16 agen JARVIS. Dapur = Hermes 1 profil + 10 topik Telegram + wiki Desktop + 5 cron. Jendela hanya membaca.

---

## Drive `Mirai-Mission-Control` — apakah sudah diterapkan?

| Berkas Drive | Di MIRAI? | Catatan |
|--------------|-----------|---------|
| `NEXORA-Prompts-Fresh-Hermes-…md` (46) | **Sebagian** | `docs/PROMPT-MAP.md`: banyak **as-delivered ke artefak paket** (fleet 3 orang, 15 surface). **Dilarang dipasang** di Mac (create-fleet, plugin, SOUL pabrik). |
| Wiki template HTML | **Sebagian** | `memory/dashboard/` + `:8899`. Jalur hidup = Desktop Niumination, bukan `~/wiki` README. |
| `how-to-give-ai-agents-persistent-memory` | **Sebagian** | wiki 9 verb, 5 cron (bukan 7). |
| `hermes-agent-tips` | Ide, bukan file | |
| Dashboard 9 MB / three.js / kota 3D | **Tidak** (sengaja `download`) | Video = itu. Konsol kita datar. |
| Hand / MediaPipe | Skrip fetch ada; **jangan** jadi janji layar | Off poros A. |
| niu-mission-control folder | **Arsip**; jangan `:5200` | README ekosistem masih menandai niu-mc P2 — itu **indeks usang**, bukan perintah hidupkan. |
| Bundle zip 23 Okt | Belum diurai di Arena | |

**Kesimpulan Drive:** prompt NEXORA **diterjemahkan jadi kode paket**, lalu **sebagian dikunci agar tidak menimpa dapur Anda**. Bukan “46/46 hidup seperti video.”

---

## Apa yang video itu *sebenarnya* tunjukkan

Urutan bab (deskripsi + transkrip):

0:00 pinch tangan, cincin 3D kru berputar; tunjuk+tahan = buka.  
2:20 Cockpit: cari agen/misi, cluster (success rate, jumlah misi, waktu rata), status hardware, **tambah agen** dari UI.  
6:23 Voice (Piper/Kokoro/ElevenLabs).  
8:38 Hand mode.  
11:56 Chat ke agen Hermes mana pun.  
12:31 Missions: bos pilih tim, setujui rencana, **pesan antar-agen live**.  
17:51 Docs = laporan panjang.  
18:30 Schedule = cron yang agen buat sendiri.  
19:17 **Agent City**: gedung per agen, biru = kerja, oranye = siap; klik = chat.  
21:03 Health CPU/RAM/disk.  
21:35 Files: SOUL.md / USER.md.  
22:06 Terminal.  
23:03 Integrasi + panduan.  
23:37 Settings tema/layout/font/model/suara.  
26:07 Cara dapat paket.

Model kru di video: **16 profil Hermes**, hiring/firing dari dashboard, kota tumbuh. Itu **bukan** model Niumination.

---

## Terjemahan ke ekosistem Anda (wajib)

Dapur (`ecosystem-config` + kunci 10 Okt):

- 1 otak Hermes (`default`). **Bukan** 16 profil. **Bukan** Executor+3 SOUL pabrik.
- 10 kursi = thread Telegram (TR 1, RS 802, BD 803, QA 804, KR 1172, SB 7402, AS 8853, CR 12595, ED 12707, OR 13902).
- Router = `config.yaml`. Plugin NEXORA **OFF**.
- Memori panjang = wiki Desktop Niumination, 9 verb, 5 cron.
- Port: MC `:8800`, wiki `:8899`. Gateway / 9router / A2A **lampu saja**.
- Produksi nyata ada di org (PemdiAcehTengah, kune-ya, edu-content, …) — jendela **jangan** pura-pura jadi niu-mc FastAPI.

| Fitur video | Padanan Niumination | Status |
|-------------|---------------------|--------|
| 16 gedung / hiring | 10 kursi tetap | Ada `house` + avatar WebP. **Tidak** tombol hire. |
| Bos pilih tim | OR #13902 pecah kerja; BD≠QA; KR≠ED | Teks tupoksi ada; **bukan** misi NEXORA live. |
| Pesan antar-agen | Topik Telegram, bukan chat localhost | **Celan terbesar.** |
| Docs tab | Wiki Desktop | Dashboard wiki terpisah `:8899`. |
| Schedule | 5 cron wiki (bukan mail/offsite) | Health/cron ticker. |
| City biru/oranye | Mosaic 10 bust: hidup/siap | Datar, bukan 3D. |
| Cockpit angka misi | Kanban boleh **kosong jujur** | Jangan seed 142 misi palsu. |
| Voice / Hand / Terminal / SOUL editor | Off-limits atau bukan prioritas | Jangan tiru dulu. |
| 127.0.0.1, state `~/mirai/data` | Sudah | Pertahankan. |
| Faces | 10 donghua-AI + still | Sudah. |

---

## Yang *boleh* menyerupai video tanpa jadi NEXORA

1. **Satu layar “kota 10 kursi”** — isometric/CSS, 10 bangunan **bernama tupoksi**, pulsa bara jika working — **tanpa** Three.js/CDN, **tanpa** tambah gedung.
2. **Cluster** = 5 cron + wiki detak + gateway lampu; success rate hanya jika data nyata.
3. Cari = cari 10 kursi / halaman wiki, bukan 16 profil.
4. Klik gedung = kartu fungsi + “buka di Telegram”, **bukan** chat Hermes palsu.

Yang **jangan** ditiru walau video keren: create-fleet, 16 agen, hand, voice cloud, bind 0.0.0.0, tulis SOUL, plugin topik, misi teatrikal.

---

## Putusan

Drive **tidak** “semua sudah jadi tujuan MIRAI sekarang.” Yang jadi: **lantai teknis** (router, db, pack, tes, avatar, house). Yang tidak jadi: **pengalaman video** (kota, misi live, tangan, hiruk 16 kru) dan **dapur Anda** (Telegram 10 topik) masih dua dunia.
