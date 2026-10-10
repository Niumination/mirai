# Hand mode's models, already here

These are the six files Hand mode loads, fetched from the two upstreams the
pack names. They are **not tracked in git** (`lib/mediapipe/` is in .gitignore):
26+ MB of somebody else's models is a download, not source.

| file | bytes | sha256 (first 16) |
| --- | --- | --- |
| `hand_landmarker.task` | 7,819,105 | `fbc2a30080c3c557` |
| `vision_bundle.mjs` | 155,439 | `d885630c297c0b20` |
| `wasm/vision_wasm_internal.js` | 323,377 | `e170ee67dd4e16c1` |
| `wasm/vision_wasm_internal.wasm` | 11,756,954 | `8da277a733926eac` |
| `wasm/vision_wasm_nosimd_internal.js` | 323,180 | `e81d715a3d42cc33` |
| `wasm/vision_wasm_nosimd_internal.wasm` | 10,960,242 | `a28483cd42e74e85` |

## Where they came from

- `vision_bundle.mjs` and the four `wasm/` files:
  `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/...`
- `hand_landmarker.task`:
  `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`

Both upstreams pin version `1.0.1` / model rev `1`. Apache-2.0 (MediaPipe, Google).

## Checking them, or getting them again

```bash
cd ~/mirai/lib/mediapipe && shasum -a 256 -c SHA256SUMS.txt   # macOS
bash ~/mirai/mission-control/scripts/fetch-mediapipe.sh       # re-fetch + verify
```

The server serves this folder at `/lib/mediapipe/...`; the dashboard asks for it
relative to itself, which is why nothing here is a CDN URL at runtime.
