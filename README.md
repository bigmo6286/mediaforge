# MediaForge

A local, open-source AI **video & image studio**. Turn a single photo into a
talking presenter video (UGC ads, tutorials, virtual presenters), generate
motion clips with **Wan**, and do fast local video/image edits — all from a
clean web UI.

```
┌────────────┐     HTTP/JSON      ┌──────────────────────────────┐
│  React UI  │  ───────────────►  │  FastAPI backend             │
│ (Vite:5173)│  ◄───────────────  │  jobs · ffmpeg · providers   │
└────────────┘                    └──────────────┬───────────────┘
                                                 │
                    local (CPU)  ◄───────────────┼───────────────►  hosted GPU
                    ffmpeg edits, image ops,     │   Wan / SadTalker / Kokoro
                    Piper TTS                     │   via fal.ai or replicate
                                       local GPU (optional): diffusers WanPipeline
```

## What it does

| Tab | Feature | Runs on |
|-----|---------|---------|
| 🎤 **Talking Avatar** | 1 photo + voice → lip-synced presenter (SadTalker/Hallo/Wan2.2-S2V). Voice from a typed **script** (TTS) or an uploaded recording. | GPU (hosted or local); TTS can run locally on CPU via Piper |
| ✨ **Motion** | Text→Video / Image→Video with **LTX-Video** (free-GPU friendly) or **Wan**. A duration slider goes to 30s — clips longer than one model window are built by **auto-chaining** segments (last frame seeds the next) and trimmed to length. | GPU (hosted or local) |
| 🎭 **Face & Wardrobe** | **Face swap** on a **photo or video** (swapped across every frame; InsightFace local or hosted) and **Dress change** (virtual try-on with IDM-VTON) | face swap: CPU/GPU · try-on: GPU (hosted) |
| 🎬 **Video Edit** | Trim, crop, resize, speed, → GIF, convert, extract frames, extract audio | **CPU, local** |
| 🖼️ **Image Edit** | Background removal, resize, format convert | **CPU, local** |

The Talking Avatar tab also has a **▶ Preview voice** button — synthesize and
hear the script (local Piper TTS) before rendering the full video.

The heavy AI models (Wan, avatar) need a GPU. This machine has none, so they run
on a **hosted GPU** (fal.ai or Replicate — pay-per-render, open-source models).
Drop in a GPU later and set `WAN_PROVIDER=local` to go fully offline — the UI
doesn't change.

## Quick start

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add an API key (see below)
uvicorn app.main:app --reload # http://127.0.0.1:8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

Or use the launcher: `./run.sh` (starts both).

### Windows

Works on Windows too (paths, the bundled ffmpeg, and Piper are all
cross-platform). Use the PowerShell scripts instead of the shell ones:

```powershell
# from the project folder
powershell -ExecutionPolicy Bypass -File run.ps1        # start backend + frontend
powershell -ExecutionPolicy Bypass -File setup_gpu.ps1  # one-shot GPU setup
```

Manual equivalent: create the venv with `python -m venv .venv`, activate via
`.\.venv\Scripts\Activate.ps1`, then the same `pip install` / `uvicorn` / `npm`
commands as above. Requires Python 3.10+ and Node 18+.

## Enabling AI generation

Local editing works out of the box. For the **Talking Avatar** and **Motion**
tabs you need one GPU backend. Pick either:

**fal.ai** (simplest)
```
# backend/.env
WAN_PROVIDER=fal
FAL_KEY=your_key_here          # https://fal.ai/dashboard/keys
```

**Replicate**
```
WAN_PROVIDER=replicate
REPLICATE_API_TOKEN=your_token # https://replicate.com/account/api-tokens
```

**Local GPU** (a machine with CUDA) — *just works, no keys*
```bash
./setup_gpu.sh     # installs base + torch/diffusers, downloads voices
./run.sh           # UI at http://localhost:5173
```
On startup MediaForge calls `torch.cuda.is_available()` and, if a GPU is found,
**auto-defaults every model to `local`** — Wan and LTX-Video run on your card via
`diffusers`, no API keys, nothing to configure. The header shows `⚡ GPU` and
`models → local`. On a machine without a GPU it stays on the hosted/CPU paths.
Override any feature explicitly with `WAN_PROVIDER` / `MOTION_PROVIDER` /
`AVATAR_PROVIDER` if you want.

For the **local talking avatar**, also set up SadTalker once:
```bash
git clone https://github.com/OpenTalker/SadTalker
# download its checkpoints per that repo's README, then:
export SADTALKER_DIR=/path/to/SadTalker
```
Local motion + TTS work without it; only the avatar tab needs SadTalker locally.

### Voice (TTS) for the avatar
- **Local, CPU, free (default):** Piper. Install and grab voices:
  ```bash
  pip install piper-tts
  python -m piper.download_voices en_US-amy-medium en_US-ryan-high en_GB-alba-medium \
      --data-dir voices
  ```
  Any `.onnx` in `backend/voices/` is auto-detected and offered in the Avatar
  tab's voice dropdown — `TTS_PROVIDER` defaults to `piper` when voices exist.
  Browse more at [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices).
- **Hosted:** set `TTS_PROVIDER=fal` (or `replicate`) to use the open **Kokoro**
  model on a GPU instead.

### Optional local extras
```
# background removal (image tab), CPU-friendly:
pip install rembg onnxruntime
```

## Model / provider config

Every model id and avatar input-field name is overridable via env vars (see
`app/config.py` and `.env.example`) — so you can point the avatar tab at
SadTalker, Hallo, or Wan2.2-S2V without touching code.

## Run it free on a GPU (no API keys)

The models are open-source; only the *hosting* costs money. To stay 100% free,
run the models yourself on a **free Colab/Kaggle T4** using
[`colab/MediaForge_FreeGPU.ipynb`](colab/MediaForge_FreeGPU.ipynb): it launches
the whole backend on the free GPU with `MOTION_PROVIDER=local` and exposes a
public URL. LTX-Video + SadTalker + Kokoro/Piper all fit a free T4. (The big
Wan-14B model does **not** fit 16 GB — use LTX or Wan-1.3B; longer clips come
from chaining, not a bigger model.)

## Notes
- These are **batch renderers** — great for pre-recorded UGC/tutorial/presenter
  clips, not live real-time video calls.
- Jobs run in an in-memory queue; state resets when the backend restarts.
- Front-facing, well-lit portraits give the best talking-avatar results.
