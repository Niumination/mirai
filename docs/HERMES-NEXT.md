# Instruksi untuk Hermes Mac — laporkan ke Arena (tahap berikutnya)

Salin blok **PROMPT** di bawah ke sesi Hermes di Mac. Jangan menerapkan perubahan baru kecuali prompt itu menyuruh **baca-saja**. Arena butuh bukti, bukan interpretasi.

Tujuan tahap berikutnya (setelah adopsi :8800 hidup):

1. Mengetahui gap nyata (health 17/20, yaml thread 1, CI, path).
2. Memutuskan apakah cockpit harus baca 10 persona yaml (bukan roster kosong).
3. Tidak merusak gateway / 9router / A2A / 10 topik.

---

## PROMPT (tempel utuh ke Hermes Mac)

```
Kamu Hermes di Mac. Baca-saja. Jangan: create-fleet, install-habits, tulis SOUL.md,
tulis profile_routes, restart ai.hermes.gateway, sentuh 9router :20128, A2A :9900,
hidupkan niu-mission-control, pasang plugin telegram_topic_profiles, hermes cron create
wiki-mail-sweep atau wiki-offsite.

Kecuali: kalau persona yaml thread 1 masih "Orkestrator" (bukan Triage/General),
itu SATU suntingan yang pemilik sudah izinkan — lakukan, lalu sertakan diff.
Jangan ubah 9 thread lain.

Kirim ke pemilik SATU laporan markdown dengan heading persis seperti di bawah.
Setiap heading: perintah yang kamu jalankan + output mentah (potong rahasia:
token, cookie, Authorization). Jangan parafrase bukti.

## 0. Identitas mesin
uname -m; sw_vers; /usr/bin/python3 --version; which python3; echo "PATH python: $(python3 --version 2>&1)"
echo HOME=$HOME
ls -ld ~/mirai ~/mirai-src ~/Desktop/Niumination/mirai ~/Desktop/Niumination/wiki ~/wiki 2>&1
git -C ~/Desktop/Niumination rev-parse --show-toplevel 2>&1
git -C ~/Desktop/Niumination/mirai rev-parse HEAD 2>&1
git -C ~/Desktop/Niumination/mirai remote -v 2>&1
git -C ~/Desktop/Niumination/wiki rev-parse HEAD 2>&1; git -C ~/Desktop/Niumination/wiki log -3 --oneline

## 1. Proses MIRAI
launchctl print gui/$(id -u)/com.mirai.mission-control 2>&1 | egrep 'state =|pid =|path =|KeepAlive|ProgramArguments' | head -40
lsof -nP -iTCP:8800 -sTCP:LISTEN
lsof -nP -iTCP:8899 -sTCP:LISTEN
# pastikan TIDAK listen 0.0.0.0
lsof -nP -iTCP:8800 -sTCP:LISTEN | cat

## 2. /api/health 17/20 — WAJIB rinci
curl -sS http://127.0.0.1:8800/api/ping
curl -sS http://127.0.0.1:8800/api/health | python3 -m json.tool
# Jika ada array checks/diagnostics: cetak SETIAP item yang bukan pass
# (nama, status, pesan). Ini yang Arena butuhkan untuk tahap cockpit.

## 3. Roster vs 10 persona
curl -sS http://127.0.0.1:8800/api/agents | python3 -m json.tool | head -c 8000
echo "--- profiles dir ---"
ls -la ~/.hermes/profiles 2>&1
hermes profile list 2>&1
# yaml: 10 thread id + persona + model. REDACT token.
python3 - <<'PY'
from pathlib import Path
import re
p = Path.home()/".hermes"
cands = list(p.glob("**/config.yaml")) + list(p.glob("**/config.yml"))
print("config files:", cands)
text = ""
for c in cands:
    t = c.read_text()
    if "802" in t or "13902" in t:
        text = t
        print("using", c)
        break
if not text:
    print("NO config with thread ids found")
else:
    for tid in ["1","802","803","804","1172","7402","8853","12595","12707","13902"]:
        print("==== thread", tid, "====")
    # print ~15 lines around first occurrence of the id as topic/thread
    lines = text.splitlines()
    for i,l in enumerate(lines):
        if re.search(r'\b%s\b' % tid, l) and i<4000:
            if "persona" in l.lower() or "thread" in l.lower() or "topic" in l.lower() or l.strip().startswith("-") or "id:" in l:
                print("\n".join(lines[max(0,i-3):i+12]))
                print("---")
PY

## 4. Cron wiki (harus 5, bukan 7)
hermes cron list
# konfirmasi ADA: wiki-dropbox wiki-librarian wiki-lint wiki-opening-snapshot wiki-closing-snapshot
# konfirmasi TIDAK ADA: wiki-mail-sweep wiki-offsite

## 5. Wiki CLI vs path ekosistem
command -v wiki; type wiki; head -40 "$(command -v wiki)"
CREW_WIKI_DIR= wiki index 2>&1 | head -20
ls -la ~/Desktop/Niumination/wiki/.git ~/wiki/.git 2>&1
# lock type: file vs directory
ls -ld ~/Desktop/Niumination/wiki/.wiki.lock ~/wiki/.wiki.lock 2>&1

## 6. Gate / host / console
ls -l ~/Desktop/Niumination/mirai/data/auth.token ~/mirai/data/auth.token 2>&1
curl -sS -D - -o /tmp/mirai-page.html -m 15 http://127.0.0.1:8800/ | head -20
wc -c /tmp/mirai-page.html
# Host asing harus 403
curl -sS -D - -o /dev/null -H 'Host: evil.example' http://127.0.0.1:8800/api/ping | head -15

## 7. Yang off-limits masih utuh
launchctl print gui/$(id -u)/ai.hermes.gateway 2>&1 | egrep 'state =|pid =' | head
lsof -nP -iTCP:9900 -sTCP:LISTEN | head
lsof -nP -iTCP:20128 -sTCP:LISTEN | head
lsof -nP -iTCP:5200 -sTCP:LISTEN | head
test -d ~/Desktop/Niumination/inactive-2026-10/niu-mission-control && echo "niu-mc archived yes"

## 8. CI ecosystem-config
cd ~/Desktop/Niumination
git log -1 --oneline
gh run list --branch main --limit 5 2>&1
# kalau b4242f0 merah: gh run view <id> --log-failed | tail -80

## 9. mac-verify (read-only)
# Pakai skrip di repo mirai yang terpasang:
bash ~/Desktop/Niumination/mirai/mission-control/tests/mac-verify.sh
# Jangan --turn kecuali pemilik bilang.

## 10. Pertanyaan yang HANYA pemilik/Hermes bisa jawab (tulis jawaban, bukan tebakan)
- Apakah yaml thread 1 sudah Triage/General?
- Apakah cockpit perlu menampilkan 10 persona dari yaml di tahap berikutnya? (Arena usul: ya, read-only)
- Path kanban.db yang dipakai gateway (find ~/.hermes -name kanban.db)
- Apakah dashboard yang dilayani GET / adalah file di mirai/dashboard.html root git atau ~/mirai/dashboard.html?
```

---

## Setelah laporan kembali ke Arena

Arena akan (tanpa sentuh Mac): merancang tahap 2 — kemungkinan **roster read-only dari 10 baris yaml**, perbaiki check health yang gagal, samakan `mac-verify` dengan 20 PASS tanpa FAIL palsu. Tidak ada create-fleet.
