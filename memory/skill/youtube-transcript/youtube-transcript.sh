#!/usr/bin/env bash
# youtube-transcript — a YouTube link into a clean, verbatim transcript.
#
# Two traps handled here because both fail quietly:
#   1. yt-dlp needs a JavaScript runtime on this machine. Without one it fetches
#      nothing for many videos and says little about it.
#   2. Auto-captions repeat themselves in overlapping fragments. They are cleaned
#      so the text reads as prose: no timestamps, no repeats.
# If a video has no captions at all, this exits non-zero and says so. The agent
# must never summarise a video it could not read.
set -euo pipefail

URL="${1:-}"
[ -n "$URL" ] || { echo "usage: youtube-transcript.sh <url> [--slug name]" >&2; exit 2; }
SLUG=""
[ "${2:-}" = "--slug" ] && SLUG="${3:-}"

command -v yt-dlp >/dev/null 2>&1 || {
  echo "yt-dlp is not installed. Install it with: brew install yt-dlp   (macOS)" >&2
  echo "or: pipx install yt-dlp" >&2
  exit 3
}

# JavaScript runtime: yt-dlp uses it for YouTube's newer signature handling.
JS_ARGS=()
if command -v node >/dev/null 2>&1; then
  JS_ARGS=(--js-runtimes node)
else
  echo "note: no node found on PATH — some videos will fail to resolve. brew install node" >&2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

META_JSON="$TMP/meta.json"
yt-dlp "${JS_ARGS[@]}" --skip-download --write-auto-subs --write-subs \
  --sub-langs "en.*,id.*,en,id" --sub-format vtt \
  --print-json --no-warnings -o "$TMP/%(id)s" "$URL" > "$META_JSON" 2>"$TMP/err" || {
    echo "could not reach this video:" >&2
    tail -3 "$TMP/err" >&2
    exit 4
  }

VTT="$(find "$TMP" -name '*.vtt' | head -1 || true)"
if [ -z "$VTT" ]; then
  echo "This video has no captions, so there is nothing to read verbatim. Refusing to summarise a video nobody could read." >&2
  exit 5
fi

python3 - "$META_JSON" "$VTT" "$SLUG" "$URL" <<'PY'
import json, re, sys, datetime

meta_path, vtt_path, slug, url = sys.argv[1:5]
try:
    meta = json.loads(open(meta_path).read().strip().splitlines()[-1] if open(meta_path).read().strip() else "{}")
except Exception:
    meta = {}

title = meta.get("title") or slug or "Untitled video"
channel = meta.get("channel") or meta.get("uploader") or "unknown"
upload = meta.get("upload_date")          # YYYYMMDD
date = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}" if upload else "unknown"
kind = "auto" if "auto" in vtt_path or meta.get("subtitles", {}) == {} else "official"

def parse_vtt(path):
    out, last = [], ""
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            continue
        if re.match(r"^\d+$", line):                       # cue number
            continue
        if "-->" in line:                                  # timing line: dropped
            continue
        text = re.sub(r"<[^>]+>", "", line)                # inline tags
        text = re.sub(r"&[a-z]+;", " ", text)
        text = " ".join(text.split())
        if not text:
            continue
        # Auto-captions repeat overlapping fragments: skip a line that is
        # already the tail of what we have.
        tail = last[-len(text):] if text else ""
        if text and (text == last or tail == text):
            continue
        if last and text.startswith(last):
            out[-1] = text
        else:
            out.append(text)
        last = out[-1]
    return out

lines = parse_vtt(vtt_path)
joined, buf = [], ""
for l in lines:                                            # reflow into prose
    buf = (buf + " " + l).strip()
    if len(buf) > 100 and buf.endswith((".", "!", "?", ":", ";")):
        joined.append(buf); buf = ""
if buf:
    joined.append(buf)

today = datetime.date.today().isoformat()
header = (f"# {title}\n"
          f"Source: {url} · By: {channel} · Published: {date}\n"
          f"Read: {today} · Type: video\n"
          f"Third-party material. These are the author's claims, not our facts.\n"
          f"(captions: {kind})\n")
print(header)
print("\n\n".join(joined))
PY
