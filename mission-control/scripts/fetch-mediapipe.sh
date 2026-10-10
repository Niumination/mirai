#!/usr/bin/env bash
# Hand mode needs six files the dashboard does not ship. Fetch them into
# ~/mirai/lib/mediapipe/, which scripts/../server serves at /lib/mediapipe/... so
# the page finds them relative to itself.
#
#   bash fetch-mediapipe.sh
#
# About 30 MB. Every curl must exit zero: a half-downloaded wasm file makes Hand
# mode fail inside the browser with nothing useful in the console, so this script
# checks sizes and, when SHA256SUMS.txt is beside the files, checks the checksums and
# refuses to call a short or corrupted download done. (The vision_bundle.mjs minimum
# is 100 KB, not a megabyte: the real file is 152 KB, and the first version of this
# script would have deleted a perfectly good download for being "short".)
set -euo pipefail

MIRAI_DIR="${MIRAI_DIR:-$HOME/mirai}"
DEST="$MIRAI_DIR/lib/mediapipe"
PIN="1.0.1"

mkdir -p "$DEST/wasm"
cd "$DEST"

fetch() {                       # fetch <url> <path> <minimum bytes>
  local url="$1" out="$2" min="$3"
  if [ -s "$out" ] && [ "$(wc -c < "$out")" -ge "$min" ]; then
    printf '  have   %s (%s bytes)\n' "$out" "$(wc -c < "$out")"
    return 0
  fi
  printf '  get    %s\n' "$out"
  curl -fsSL "$url" -o "$out"
  local got; got="$(wc -c < "$out")"
  if [ "$got" -lt "$min" ]; then
    echo "  SHORT  $out is $got bytes, expected at least $min — deleting it" >&2
    rm -f "$out"
    exit 1
  fi
}

verify() {                      # verify <path>  — against SHA256SUMS.txt when present
  local out="$1" want got
  [ -f "SHA256SUMS.txt" ] || return 0
  want="$(awk -v f="$out" '$2 == f {print $1}' SHA256SUMS.txt)"
  [ -n "$want" ] || return 0
  if command -v sha256sum >/dev/null 2>&1; then
    got="$(sha256sum "$out" | awk '{print $1}')"
  else
    got="$(shasum -a 256 "$out" | awk '{print $1}')"     # macOS has shasum, not sha256sum
  fi
  if [ "$got" != "$want" ]; then
    echo "  BAD    $out does not match the pinned checksum — deleting it" >&2
    rm -f "$out"
    exit 1
  fi
  echo "  good   $out matches its checksum"
}

echo "==> Hand mode models into $DEST"
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@$PIN/vision_bundle.mjs" \
       vision_bundle.mjs 100000
fetch "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" \
       hand_landmarker.task 5000000
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@$PIN/wasm/vision_wasm_internal.js" \
       wasm/vision_wasm_internal.js 100000
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@$PIN/wasm/vision_wasm_internal.wasm" \
       wasm/vision_wasm_internal.wasm 5000000
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@$PIN/wasm/vision_wasm_nosimd_internal.js" \
       wasm/vision_wasm_nosimd_internal.js 100000
fetch "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@$PIN/wasm/vision_wasm_nosimd_internal.wasm" \
       wasm/vision_wasm_nosimd_internal.wasm 5000000

total="$(du -sk "$DEST" | cut -f1)"
echo
echo "==> All six in place, $((total / 1024)) MB total:"
ls -la "$DEST" "$DEST/wasm" | grep -E 'vision_|hand_landmarker' | sed 's/^/  /'
echo
echo "The server serves them at /lib/mediapipe/... — no restart needed, it reads per request."
echo "==> verifying what is on disk"
for f in vision_bundle.mjs wasm/vision_wasm_internal.js wasm/vision_wasm_internal.wasm \
         wasm/vision_wasm_nosimd_internal.js wasm/vision_wasm_nosimd_internal.wasm \
         hand_landmarker.task; do
  verify "$f"
done

echo "Proof:  curl -s -o /dev/null -w '%{http_code} %{content_type}\\n' http://127.0.0.1:8800/lib/mediapipe/hand_landmarker.task"
echo "Then open Hand mode and press \"Start the camera\"."
