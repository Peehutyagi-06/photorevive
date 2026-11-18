# PhotoRevive — Local Image & Video Enhancement

This is a beginner-friendly first version: FastAPI (Python) backend + plain HTML/CSS/JavaScript frontend. It deliberately avoids React, NumPy, Docker, PostgreSQL and Homebrew.

## What works
- Upload JPG, PNG or WEBP (max 10 MB)
- Validate image files on the backend
- Enlarge the image to 4× width and height
- Preview and download the result

**Important:** this starter uses Pillow Lanczos resizing. It is not Real-ESRGAN and does not invent AI details. Once this runs, we can add the pretrained AI model as a separate step.

## Run on Mac
Open VS Code terminal in the folder containing `requirements.txt`.

1. Check Python:
   `python3 --version`
2. Create environment:
   `python3 -m venv .venv`
3. Activate it:
   `source .venv/bin/activate`
4. Install packages:
   `python -m pip install --upgrade pip`
   `python -m pip install -r requirements.txt`
5. Start:
   `python -m uvicorn app.main:app --reload`
6. Open http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs
Health check: http://127.0.0.1:8000/api/health

Stop the server with Control+C.

## Structure
- `app/main.py` — backend
- `app/frontend/index.html` — page
- `app/frontend/style.css` — design
- `app/frontend/script.js` — upload and result interactions
- `requirements.txt` — four Python packages

If Python is not installed, install Python 3.11 from https://www.python.org/downloads/macos/, then reopen VS Code. No Homebrew is required.
