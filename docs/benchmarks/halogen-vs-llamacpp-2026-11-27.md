# Halogen vs llama.cpp on framework-desktop — 2026-11-27

Status: measured with the image's own tools on 2026-11-27. All numbers below are tok/s.

| Arm | Drafted decode (tok/s) | Serial decode (tok/s) | Prefill 8192 (tok/s) | Prefill 32768 (tok/s) | Notes |
|---|---:|---:|---:|---:|---|
| Published Halogen 0.21.0 ht4 | 37.9 | 15.1 | 605 | 530 | 128 GB reference box, kernel 7.0, ~85 W; published 2K prefill was 578; cache **on**, prompts new to it |
| Measured llama.cpp Swift Q6_K / Vulkan RADV | 23.9 | not measured | 330 | 280 | Live pod before cutover; 2K prefill was 347 |
| Measured Halogen 27B ht4 (this box) | 39.10 | 13.2 | 665.97 | 587.76 | `sweep tg128` drafted decode ±7.16; serial is a wall-clock median of 30 runs (not engine t/s); prefill is cold, cache **off** |
| Attempted Halogen Swift Q6_K GGUF | — | — | — | — | Refused: `gguf: architecture 'qwen35': this engine reads qwen4exp (Qwen3.8-Flash-Next) only` |

## Measurements

- Decode (`HALOGEN_API=http://127.0.0.1:8731 HALOGEN_API_LOG=/tmp/halogen-api.log python3 /halogen/tools/bench-serving.py serial,mtp 256 low 3`, 10 cases x 2 drafters x 3 reps): drafted `mtp` mean **31.63 t/s**, commit 3.26/round, min 21.40 / max 44.64; identity check passed (every drafter byte-identical on every case). Serial is non-speculative, so the tool emits no engine ledger line and marks those rows `*` (wall-scored): median **13.2 t/s** over 30 runs, with several stalling at 0.5–5.3 t/s on this shared node.
- Cold prefill (`python3 /halogen/tools/halogen-bench.py --api http://127.0.0.1:8731 -p 8192,32768 -n 128`, 3 reps): `pp8192` **665.97 ± 4.70** (661.0–670.3), `pp32768` **587.76 ± 1.72** (586.0–589.4), `tg128` **39.10 ± 7.16** (29.4–48.8). The table uses `tg128` for drafted decode because that is the published arm's instrument; the `bench-serving.py` mtp mean is 31.63 t/s on a different prompt set.
- Raw output: `/tmp/halogen-bench.txt`, `/tmp/halogen-sweep.txt` from the run session.

## Configuration

- Image: `ghcr.io/peonist-ai/halogen-flash-server:0.21.0`.
- Kept 1:1 with published defaults: `HALOGEN_CTX=262144`, `HALOGEN_PROMPT_CACHE=2`, `HALOGEN_KV_SLOTS=4`.
- Forced deviations on the 64 GB box: `HALOGEN_KV_POOL_POSITIONS=262144` (not 524288), `HALOGEN_HOST_RESERVE_GIB=8` (not 20).
- Actual pool from `/health`: `kv_pool_positions: 262144`, `slot_ctx: 262144`, `slots: 4`; `checkpoint_format: hgn`. No `LOWERING THE POOL TO N` line appeared. Startup reported 12.8 GiB weights, 18.3 GiB KV pool, 13.5 GiB working memory, leaving 7.3 GiB host-contiguous blocks.
- Cache-off for cold prefill: temporary `HALOGEN_PROMPT_CACHE=0` on the serving Deployment, then restored — `/health` reports `prompt_cache: enabled=True, cap_mb=147, mode=2` and the Deployment has no explicit cache env.
- No second engine was started: both tools targeted the already-serving API at `127.0.0.1:8731`.

## Follow-up

Investigate getting the Swift Q6_K weights running on Halogen. The 0.21.0 blocker is architectural (`qwen35` vs `qwen4exp`), so look at other Halogen versions/engines or a conversion path that preserves the Swift weights; do not report it as done until it starts and serves.

## Caveats

- Published numbers come from a 128 GB machine at about 85 W; this is a 64 GB unified-memory k3s worker sharing the APU with other pods.
- The original GGUF question could not be answered on this image: Halogen 0.21.0 refuses `qwen35` GGUFs. The measured arm uses the engine's 27B ht4 checkpoint, so it tests the engine but not our GGUF weights.
- Published prefill used the cache **on** with each prompt new to it; the measured prefill used the cache **off** as specified, so it is colder than the published arm. Published decode numbers use the engine's `bench`/`sweep` instruments; the serial number here is wall-scored and includes prefill and queueing, so compare it loosely.
- Repeated prompts were avoided; they can inflate drafted decode to ~152 tok/s at 100% draft acceptance.
