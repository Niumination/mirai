# 10 topik Niu-MissionControl — fakta, fungsi, usulan

Grup: **Niu-MissionControl** `chat_id: -1004204696417` (forum, `can_manage_topics: true`).

Id topik **tidak diubah di paket ini**. Pemilik **menyetujui** usulan fungsi di bawah (2026-10-10): 7402 = sandbox; 1 vs 13902 tidak digabung; 1172 vs 12707 tidak digabung; 12595 tetap noise cron. Hermes Mac **boleh** mengubah persona yaml thread **1** dari “Orkestrator” menjadi **Triage / General** (satu-satunya tulis yaml yang diizinkan di adopsi ini).

Plugin `telegram_topic_profiles` **tetap OFF**. `config.yaml` tetap router. Berkas `fleet/plugins/telegram_topic_profiles/topics.json` diisi sebagai **peta id → label**, bukan sebagai router hidup.

---

## Fakta sekarang (jangan diarang)

| Id | Nama yang kamu kirim | Persona di yaml | Model / provider | Binding yaml (banyak tidak resolve) |
| --- | --- | --- | --- | --- |
| 1 | General | Orkestrator | gemini-3.5-flash-lite / 9router | — |
| 802 | Research | Researcher | combo-delegasi / 9router | — |
| 803 | Builder | Builder | kr/deepseek-3.2 / 9router | ponytail, code-review |
| 804 | QA | Pengawas | combo-delegasi / 9router | **code-audit** (dulu `codebase-audit`; sudah diperbaiki di Mac) |
| 1172 | Kreator | Kreator | combo-delegasi / 9router | ghost, humanizer, remotion |
| 7402 | Serbaguna | Serbaguna | combo-delegasi / 9router | — |
| 8853 | ASN | Admin Dinas ASN | sensenova-6.8-flash-lite / **huancheng** | skp-kinerja, meeting, weekly |
| 12595 | Cron & Otomasi | Cron & Otomasi | combo-delegasi / 9router | — |
| 12707 | Edu Content | Edu Content | combo-delegasi / 9router | doc-pipeline, markitdown, remotion, ghost |
| 13902 | Orkestrator | Orkestrator | combo-gateway / 9router | subagent-dev, kanban, router-orch |

Dua label “Orkestrator” (1 dan 13902) + 7402 tanpa skill + 1172/12707 berbagi ghost+remotion = fungsi tidak maksimal.

---

## Fungsi yang diusulkan (id tetap)

Tujuan: setiap topik punya **satu pekerjaan yang tidak bisa dicuri topik lain**.

| Id | Nama UI | Fungsi maksimal | Bukan ini |
| --- | --- | --- | --- |
| **1** | General | Inbox manusia: sapaan, “ini masuk topik mana?”, triage satu kalimat. Model murah (flash-lite) **tepat**. Tidak mendelegasi, tidak nulis kode, tidak kanban. | Bukan bos kru |
| **13902** | Orkestrator | Satu-satunya bos: pecah kerja, kanban, subagent, pilih topik tujuan. Manusia yang minta “kerjakan X” diarahkan ke sini, bukan ke 1. | Bukan chat basa-basi |
| **802** | Research | Cari, kutip, provenance, halaman `wiki file research`. Tidak menulis kode produksi. | Bukan Builder |
| **803** | Builder | Ubah kode / repo. Satu PR, satu diff. | Bukan yang meng-QA hasil sendiri sebagai putusan akhir |
| **804** | QA | Review, tes, audit. Putusan “lolos/tidak”. Binding yang benar: yang **resolve** (bukan nama `codebase-audit` yang tidak ada) — urusan skill di Mac. | Bukan yang menulis fitur |
| **1172** | Kreator | Brand, copy, humanizer, video/kampanye (remotion **non-pelajaran**). | Bukan kurikulum / slide dinas |
| **12707** | Edu Content | Kurikulum, doc-pipeline, markitdown, video **pelajaran**. Remotion milik Edu hanya untuk materi ajar. | Bukan konten brand |
| **8853** | ASN | SKP, rapat, weekly dinas Aceh Tengah. Provider **huancheng** jangan dipindah ke 9router tanpa keputusanmu. Tidak ada kode, tidak ada edu umum. | Bukan Serbaguna |
| **12595** | Cron & Otomasi | Hanya laporan otomatis / gagal job / heartbeat. **Bukan** tempat manusia minta “bikin skrip”. Skrip = 803. Jadwal = Orkestrator 13902 yang menugaskan. | Bukan Builder, bukan inbox |
| **7402** | Serbaguna | **Sandbox / eksperimen** (model baru, prompt acak, “coba dulu”). Output yang berguna **wajib** dipindah ke topik spesialis lalu di-file wiki. Kalau tidak, topik ini bak sampah yang mengalahkan 802/803/1172. | Bukan “semua yang malas pilih topik” |

---

## Usulan gabung / pecah (kamu yang eksekusi di Telegram)

Tidak ada id baru di paket. Kalau setuju, kerjakan di grup; kalau tidak, biarkan id dan pakai fungsi di tabel atas.

1. **Jangan gabung 1 + 13902.** Itu dua peran. Yang salah hanya **nama**: topik 1 jangan dipanggil Orkestrator di yaml — persona yaml untuk thread 1 = “Triage / General”. Hermes Mac yang mengubah yaml **hanya jika kamu izinkan** (sekarang yaml off-limits).
2. **Jangan gabung 803 + 804.** Pemisahan penulis vs pengawas adalah nilai kru.
3. **Jangan gabung 1172 + 12707.** Pecah **remotion/ghost**: Kreator = kampanye; Edu = materi ajar. Binding yaml disesuaikan di Mac (setelah skill ambigu beres).
4. **7402 — pilih satu:**
   - **A (disarankan):** tetap id, fungsi = sandbox saja (tabel).
   - **B (gabung):** arsipkan topik di Telegram, manusia yang nyasar diarahkan ke 1. Hanya jika kamu memang tidak butuh bak eksperimen.
5. **12595 — jangan gabung ke 803.** Biarkan id untuk noise cron. Pin aturan: pesan manusia di 12595 dijawab satu baris “pindah ke 13902 atau 803” lalu diam.
6. **Tidak usul topik baru** (tidak ada “Legal”, “Keuangan”, dll.) sampai 10 ini dipakai bersesi nyata. Kanban masih 0.

---

## Binding skill

**Sudah beres di Mac (2026-10-10):** 0 duplikat, 13 binding resolve. Arena tidak merapikan bank. 804 memakai `code-audit`.

Kalau suatu saat ambigu kembali: jangan `external_dirs` ganda; loader roots harus satu.

---

## Yang masuk `topics.json` di paket

`chat_id` + 9 id berangka (General **sengaja tidak** di map: pesan tanpa thread id = agent utama — itu cocok dengan fungsi inbox topik 1 / main agent). Nilai = **label Niumination**, bukan research/writer/developer.

Ini **bukan** menghidupkan plugin.
