# MediaForge

A local, open-source AI **video & image studio**. Turn a single photo into a
talking presenter video (UGC ads, tutorials, virtual presenters), generate
motion clips with **Wan**, and do fast local video/image edits — all from a
clean web UI.

One server on **http://127.0.0.1:8000** serves both the React UI and the API:

```
                 http://127.0.0.1:8000
┌──────────────────────────────────────────────────────┐
│  FastAPI backend  (serves the built React UI + API)   │
│  jobs · ffmpeg · providers                            │
└──────────────────────────┬───────────────────────────┘
                           │
      local (CPU)  ◄───────┼───────►  hosted GPU              local GPU (auto)
      ffmpeg edits,        │   Wan / LTX / SadTalker / Kokoro   diffusers
      image ops, Piper TTS │   via fal.ai or replicate          Wan/LTX pipelines
```

## What it does

| Tab | Feature | Runs on |
|-----|---------|---------|
| 🎤 **Talking Avatar** | 1 photo + voice → lip-synced presenter (SadTalker/Hallo/Wan2.2-S2V). Voice from a typed **script** (TTS) or an uploaded recording. | GPU (hosted or local); TTS can run locally on CPU via Piper |
| ✨ **Motion** | Text→Video / Image→Video with **LTX-Video** (free-GPU friendly) or **Wan**. A duration slider goes to 30s — clips longer than one model window are built by **auto-chaining** segments (last frame seeds the next) and trimmed to length. | GPU (hosted or local) |
| 🎭 **Face & Wardrobe** | **Face swap** on a **photo or video** (every frame; InsightFace), an optional **GFPGAN face-restore pass** to sharpen results, standalone **Restore faces** for any blurry photo/video, and **Dress change** (virtual try-on, IDM-VTON) | face swap/restore: CPU/GPU · try-on: GPU (hosted) |
| 🎬 **Video Edit** | Trim, crop, resize, speed, → GIF, convert, extract frames, extract audio | **CPU, local** |
| 🖼️ **Image Edit** | Background removal, resize, format convert | **CPU, local** |

The Talking Avatar tab also has a **▶ Preview voice** button — synthesize and
hear the script (local Piper TTS) before rendering the full video.

The heavy AI models (Wan, avatar) need a GPU. This machine has none, so they run
on a **hosted GPU** (fal.ai or Replicate — pay-per-render, open-source models).
Drop in a GPU later and set `WAN_PROVIDER=local` to go fully offline — the UI
doesn't change.

## Quick start

**One command, one server, one URL** — the backend builds and serves the UI, so
you open a single address: **http://127.0.0.1:8000**

```bash
./run.sh          # macOS / Linux
```
```powershell
powershell -ExecutionPolicy Bypass -File run.ps1   # Windows
```

That installs deps, builds the frontend, and starts the server. When it prints
`http://127.0.0.1:8000`, open that. **Not** `:5173` — that port only exists in
dev mode below.

### Windows — step by step

1. **Install the prerequisites** (once):
   - [Python 3.10+](https://www.python.org/downloads/windows/) — at the start of
     the installer, tick **“Add python.exe to PATH”**.
   - [Node.js 18+ (LTS)](https://nodejs.org/en/download) — the default installer
     is fine.
   - [Git for Windows](https://git-scm.com/download/win) (to clone the repo).
   - Reopen PowerShell afterward so the new PATH takes effect.

2. **Get the code** (in PowerShell):
   ```powershell
   git clone https://github.com/bigmo6286/mediaforge.git
   cd mediaforge
   ```

3. **Run it** (installs deps, builds the UI, starts the server, opens the browser):
   ```powershell
   powershell -ExecutionPolicy Bypass -File run.ps1
   ```
   Leave that window open. When it says `http://127.0.0.1:8000`, the app is up.

4. **Add your API key** in the app’s ⚙ **Settings** tab (or skip — local voice and
   all editing work with no key). To stop the app, press **Ctrl+C** in the window.

> First run takes a few minutes (it installs Python + Node packages). Later runs
> start in seconds. If PowerShell blocks the script, the `-ExecutionPolicy Bypass`
> in the command above already handles it — run the whole line as shown.

Manual steps on Windows, if you'd rather not use the script:
```powershell
cd frontend; npm install; npm run build
cd ..\backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
# then open http://127.0.0.1:8000
```

### Manual (macOS / Linux)

```bash
cd frontend && npm install && npm run build   # produces frontend/dist
cd ../backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                          # optional; or use the ⚙ Settings tab
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open **http://127.0.0.1:8000**. Requires Python 3.10+ and Node 18+.

> **Getting a 404?** You opened the API-only mode without a built UI. Run
> `npm run build` in `frontend/` (or just use `./run.sh` / `run.ps1`), then
> reload http://127.0.0.1:8000.

### Dev mode (hot reload, optional)

For live-editing the frontend, run the two servers separately — Vite proxies
`/api` to the backend:
```bash
cd backend && uvicorn app.main:app --reload          # :8000
cd frontend && npm run dev                            # :5173  <- open this in dev
```

## Enabling AI generation

**Easiest: the ⚙ Settings tab in the app.** Paste your API key, pick the
provider, and hit Save — it writes `backend/.env` (git-ignored, `0600` perms)
and applies instantly, no restart. Each field has a hint and a "get key" link.

Local editing works out of the box. For the **Talking Avatar** and **Motion**
tabs you need one GPU backend. Pick either (via Settings, or by editing `.env`):

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
./setup_gpu.sh     # macOS / Linux: installs base + torch/diffusers, downloads voices
./run.sh           # then open http://127.0.0.1:8000
```
```powershell
powershell -ExecutionPolicy Bypass -File setup_gpu.ps1   # Windows GPU setup
powershell -ExecutionPolicy Bypass -File run.ps1
```
> **GPU not detected?** The normal `run.ps1` / `run.sh` install only the light
> stack — **PyTorch is not included** (it's ~2.5 GB), so `torch.cuda.is_available()`
> is false and models stay on the hosted/CPU path. Run **`setup_gpu.ps1`** (Windows)
> or **`setup_gpu.sh`** once to install the CUDA build of PyTorch + the model
> stack; it prints `CUDA available: True` and the GPU name when it worked. Needs
> an **NVIDIA** GPU + current driver (AMD/Intel aren't supported by the CUDA build).

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

## Run it free on a GPU (Google Colab)

No local GPU (or too little VRAM)? Run the models on Colab's **free T4 (16 GB)** —
motion generation runs there for free, no API keys. Your own machine isn't even
needed beyond a browser.

**Steps:**

1. Open the notebook in Colab (one click):
   👉 **[Open MediaForge in Colab](https://colab.research.google.com/github/bigmo6286/mediaforge/blob/main/colab/MediaForge_FreeGPU.ipynb)**
2. Turn on the GPU: **Runtime → Change runtime type → Hardware accelerator → GPU → Save**.
3. Run the cells top to bottom (Shift+Enter on each). Cell 2 installs deps (~2 min).
4. The **last cell prints a link** — click it to open MediaForge in your browser.
5. Go to the **Motion** tab, type a prompt, and Generate. The first run downloads
   the model weights (a few minutes); after that it's fast. Keep the Colab tab open.

Notes:
- **Motion (text/image → video)** works out of the box on the free GPU.
- **Talking Avatar** needs SadTalker set up separately — the easy route for
  avatars is a small hosted credit (add a fal key in **⚙ Settings**).
- Free Colab sessions time out after a while / the GPU can be busy at peak times;
  just rerun the cells for a fresh session.

## Notes
- These are **batch renderers** — great for pre-recorded UGC/tutorial/presenter
  clips, not live real-time video calls.
- Jobs run in an in-memory queue; state resets when the backend restarts.
- Front-facing, well-lit portraits give the best talking-avatar results.
