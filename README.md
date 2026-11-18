# PhotoRevive

PhotoRevive is a local FastAPI image and video restoration studio built with a plain HTML, CSS, and JavaScript frontend.

## Features

- JPG, PNG, and WEBP image enhancement
- MP4, MOV, and WEBM video enhancement
- 2× and 4× output scaling
- Adjustable detail strength
- Adaptive denoising, edge sharpening, and local contrast enhancement
- Source-quality estimation
- Original previews and downloadable enhanced results

Image processing uses Pillow, NumPy, and OpenCV. It is classical restoration, not generative AI or Real-ESRGAN.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Deploy

This repository includes `render.yaml` for Render.com and `Procfile` for compatible Python hosts.

1. Push the repository to GitHub.
2. Create a new Render Web Service from the repository.
3. Render detects `render.yaml` and installs `requirements.txt`.
4. Use the generated HTTPS URL.

## API

- `GET /api/health` — service status
- `POST /api/enhance` — enhance an uploaded image or video
