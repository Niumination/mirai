# MIRAI — paket siap-deploy untuk ekosistem niumination

Semua yang ada di folder Drive **Mirai-Mission-Control** dikerjakan di sini sebagai
**kode**, bukan sebagai daftar prompt. Tinggal install ke Mac-nya Hermes.

Tiga lapis, dibangun berurutan, masing-masing berguna sendiri:

| Lapis | Isi | Folder |
| --- | --- | --- |
| **1. Memori (Agent OS wiki)** | wiki markdown di `~/wiki`, perintah `wiki` 9 verb (dengan lock + penolakan + commit per-verb), skill `wiki` & `youtube-transcript`, pipeline `raw/_inbox`, 7 cron job malam, dashboard wiki | `memory/` |
| **2. Fleet (profil + routing Telegram)** | Executor + 3 spesialis (Research, Content Writer, Developer), SOUL masing-masing, installer habits, plugin `telegram_topic_profiles` | `fleet/` |
| **3. Mission Control** | backend Python 3 **stdlib only**, 54 route, 15 surface, LaunchAgent, backup harian, konsol dashboard satu file | `mission-control/` |

Dokumen pendamping:

- `AGENTS.md` — catatan agen + skills proyek di `.agents/skills/` (bukan `npx autoskills`, bukan `~/.hermes/skills`).
- `docs/ADOPT-MAC.md` — **baca dulu** sebelum apply di Mac (larangan create-fleet / SOUL / yaml).
- `docs/HERMES-NEXT.md` — prompt baca-saja untuk Hermes Mac (bukti tahap berikutnya).
- `docs/MAC-STATE.md` — status Mac pra-adopsi (skill 0 duplikat, niu-mc arsip).
- `docs/TOPIK-NIUMINATION.md` — 10 topik forum nyata + usulan fungsi/gabung.
- `docs/00-ARSITEKTUR.md` — bagaimana ketiganya terhubung.
- `docs/DEPLOY-MAC.md` — urutan install teknis + bukti; saring dengan ADOPT-MAC.
- `docs/PROMPT-MAP.md` — **SEMUA prompt dari 3 pack dipetakan ke artifact**, termasuk
  yang sengaja ditolak dan alasannya (mis. systemd → launchd).

## Adopsi Niumination (bukan 60 detik generik)

**Jangan** jalankan `create-fleet.sh` atau `install-habits.sh`. Satu profile `default`, `config.yaml` menang, plugin Telegram OFF. Langkah + checklist: `docs/ADOPT-MAC.md`.

```bash
# yang boleh (setelah baca ADOPT-MAC):
bash mission-control/scripts/install-mac.sh     # :8800 + LaunchAgent com.mirai.* saja
# wiki: skeleton → ~/wiki, wiki.sh di PATH, 5 cron (bukan mail-sweep/offsite)
```

Wiki: salin `memory/wiki-skeleton/` → `~/wiki/`, install `memory/skill/wiki/wiki.sh`
sebagai `wiki` di PATH, lalu jalankan `wiki index`.

## Yang TIDAK bisa saya kirim sebagai file

- **Halaman dashboard jadi** (1 file ±9 MB, berisi semua CSS/JS/xterm/three.js).
  Itu file unduhan produk, bukan kode yang bisa ditulis ulang. Backend ini
  menjawab tepat di shape yang halaman itu harapkan: taruh di
  `~/mirai/dashboard.html`, reload, langsung jalan tanpa restart.
  Sebagai gantinya saya sertakan konsol MIRAI yang sudah saya uji
  (`mission-control/web/dashboard.html`): 15 halaman, tanpa CDN.
- **Kartu opsional Hand mode** — model MediaPipe-nya (6 berkas, 30 MB) **sudah ada**
  di `lib/mediapipe/` bersama `SHA256SUMS.txt`, jadi Hand mode jalan tanpa unduhan.
  Yang tetap tidak ikut ke git adalah modelnya (`lib/mediapipe/` di-ignore — 30 MB
  milik orang lain itu unduhan, bukan source); untuk klon dari repo:
  `bash mission-control/scripts/fetch-mediapipe.sh`, yang memverifikasi sha256.
- **Kredensial & id milikmu** (token Telegram, chat id, dst) — file yang butuh
  itu sudah menyebutkannya sebagai placeholder + cara mengambilnya.

## Sudah diuji di sini (bukan klaim)

- `mission-control/tests/prove.sh` (jalankan ulang kapan saja) — semua 17 GET,
  semua penolakan (bad action, `../` traversal, body bukan JSON, array JSON,
  >30 MB → 413), siklus hidup misi NX-1001, terminal SSE, 405/404.
  Hasil: **0 traceback**. Keduanya membangun crew percobaan sendiri
  (`tests/fixture.sh`): `/tmp` tidak bertahan setelah reboot, dan `~/.hermes`
  yang hilang akan terbaca seperti kegagalan.
- `mission-control/scripts/restart.sh`: dijalankan di sini pada jalur tanpa
  LaunchAgent — pid lama ditukar, `/api/ping` menjawab sebelum script bilang
  "berhasil".
- Halaman `GET /` + `/lib/mediapipe/...` (mediapipe), ETag/304, gzip.
- `memory/dashboard/server.py` — buktinya sendiri: `bash memory/dashboard/tests/wiki-e2e.sh`
  (9 blok, semuanya cocok): halaman byte-sama dengan file, `/api/data`,
  `/api/memory/page` (tembus path 400, halaman hilang 404), drop door (link, file,
  nama jahat ditolak, tabrakan nama tidak menimpa, jendela 5 detik), `lint-now` +
  rate limit, `commit` dengan identity-nya sendiri, cookie `HttpOnly; SameSite=Strict`,
  Host allowlist, 405 + `Allow`, klien yang menggantung tidak meninggalkan traceback.
  Dua halaman milik server (fallback + `/upload`) sudah bergaya template yang sama.
- `wiki.sh`: 8 verb, hash guard, penolakan, `delete` → `processed/_deleted/`.
- Konsol MIRAI `web/dashboard.html`: dijalankan di Node dengan DOM jaring palsu →
  **15 halaman render, 0 error**, dan semua `fetch` di halaman cocok dengan route
  yang terdaftar (54 route). Tampilannya bisa dilihat sekarang juga, tanpa install:
  buka `mission-control/web/ui-preview.html` di browser mana pun (satu file, data
  contoh, tanpa CDN — 15 halaman itu juga, tinggal klik rail-nya).
- `plist` launchd di-parse ulang (ketemu 1 bug XML yang akan membuat `launchctl
  bootstrap` gagal — sudah dibetulkan).
- **Gate token (prompt 43)** — diuji ulang di `prove.sh` (port 8803): halaman tanpa
  token → halaman sign-in (200), API tanpa token → JSON 401, token benar lewat
  `X-Auth-Token` **dan** `Bearer` → 200, tautan `?k=` memasang cookie **dan cookie itu
  sendiri sudah cukup** untuk halaman + API, token salah → 401, `/api/ping` tetap
  terbuka, file token 0600, dan **token tidak pernah muncul di log**. Diuji juga
  pembalikannya: tanpa gate semua itu 200 seperti biasa.
- **Host allowlist (prompt 42)** — `Host: evil.example` → 403 pada server yang telanjang;
  begitu `MIRAI_HOSTS` menyebut nama tailnet, nama itu 200 di instance lain,
  `evil` tetap 403. 0 traceback di semua server uji.
- **Tiga halaman ini tidak menanyakan apa pun ke internet**: `dashboard.html`,
  `ui-preview.html`, `wiki-page.html` — nol referensi `http(s)` di `src`/`href`.
  Tailwind-nya hasil build dari config halaman itu sendiri, ketiga jenis huruf
  di-inline sebagai woff2 `data:` URI, dan 21 ikon Lucide yang dipakai ikut di dalam
  berkas (shim `createIcons()` dengan API yang sama). Cara mengulanginya:
  `memory/dashboard/BUILD-NOTES.md`.
- **Bug yang tidak kelihatan sampai skripnya benar-benar jalan**: keempat `<script>`
  di halaman wiki membawa `type="36bf…-text/javascript"` (sisa Cloudflare dari
  template yang diunduh dari web). Tipe itu bukan MIME JavaScript, jadi browser
  memperlakukannya sebagai data dan **tidak menjalankan satu pun** — halaman itu
  selama ini hanya markup. Setelah tipe itu dibuang, satu error sintaks yang selama
  ini tersembunyi (string dengan baris baru di dalamnya) ikut ketahuan dan dibetulkan.
  Sekarang: `node --check` bersih, dan jsdom menjalankan halamannya — **23 ikon jadi
  `<svg>`, tree render, satu halaman termuat, 0 error**.
- Rincian lengkap + daftar yang wajib dibuktikan di Mac: `docs/STATUS-UJI.md`.

## Bukti terakhir: di Mac kamu, satu perintah

```bash
bash mission-control/tests/mac-verify.sh          # ~10 detik, tidak mengubah apa pun
bash mission-control/tests/mac-verify.sh --turn   # + satu turn agen sungguhan
```

## Aturan yang dipegang di seluruh build

1. **Jangan pernah bind ke 0.0.0.0** — semua service 127.0.0.1, Tailscale di depan.
2. **State hanya di `~/mirai/data/`**; `~/.hermes` read-only kecuali 3 kasus yang
   diizinkan (cron store; file editable dengan backup; login agent baru).
3. **JSON selalu `{"ok": true|false}`** + `ApiError(status, message)`.
4. **Buktikan dengan menjalankan**, bukan "seharusnya jalan".
