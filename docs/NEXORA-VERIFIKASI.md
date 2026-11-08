# Verifikasi denah (bukan 100 loop kosong)

Iterasi bermakna = cek invariant terhadap file, bukan mengulang prompt. 2026-11-08.

## Hasil mesin (workspace)

44/44 cek kode lulus: 10 kursi house = TOPIK; plugin `off`; chat_id `-1004204696417`; 9 id di `topics.json` tanpa `1`; 5 cron wanted + 2 forbidden di `house.py`; 10 webp + 10 still; `?still=1`; wiki cascade Desktop; `/api/house` di dashboard.

## Nav aktual vs playbook

| id | Nav sekarang | Playbook F1 |
|----|----------------|-------------|
| cockpit, agents, schedule, health, files, settings | terlihat | tetap |
| **chat**, **integrations** | **terlihat** | F1: sembunyi atau relabel (bukan saingan Telegram) |
| deploy, city, missions, docs, terminal, voice, hand | hidden | tetap hidden |

Ini **satu-satunya gap denah vs UI** yang sudah diukur.

## Yang tidak bisa 100% dari Arena

- Telegram di Mac benar membuka topik
- Wiki Desktop ada dan heartbeat
- 5 cron terpasang (house hanya *baca* `jobs.json` Hermes)
- Gateway hidup
- Cache browser pack 86400

Itu F6, bukan F0.

## Klaim yang dikoreksi

- Wiki bukan “hanya Desktop”: ada fallback `CREW_WIKI_DIR` lalu `~/wiki`.
- General tidak di peta plugin; tetap kursi TR / thread 1.
- Chat localhost masih di nav — belum “sempurna” sampai F1.

## Keyakinan

- **Denah + anti-tujuan + 10 kursi + pack avatar:** cukup untuk F1.
- **“100% seperti video NEXORA”:** ditolak — itu salah tujuan.
- **“100% MIRAI melebihi video untuk rumah ini”:** setelah F1–F4 di Mac, bukan sekarang.

Jangan 100 iterasi generate. Satu matriks di atas + F1.
