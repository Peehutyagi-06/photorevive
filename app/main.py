from pathlib import Path
from uuid import uuid4
from io import BytesIO

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from fastapi.exceptions import RequestValidationError

BASE = Path(__file__).resolve().parent
FRONTEND = BASE / "frontend"
OUTPUTS = Path("/tmp") / "photorevive"
OUTPUTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PhotoRevive API")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v", "video/webm"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": "Invalid upload or form field.", "errors": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unexpected_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"Processing failed: {type(exc).__name__}: {str(exc)}"})


@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "PhotoRevive enhancement engine is running"}


def quality_score(rgb: np.ndarray) -> dict:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    p1, p99 = np.percentile(gray, (1, 99))
    contrast = float(p99 - p1)
    estimated_quality = max(0, min(100, round(35 + min(blur / 10, 35) + min(contrast / 4, 30))))
    return {
        "estimated_quality": estimated_quality,
        "sharpness": round(float(blur), 1),
        "contrast": round(contrast, 1),
    }


def enhance_image(rgb: np.ndarray, scale: int, strength: float) -> np.ndarray:
    h, w = rgb.shape[:2]
    target = (max(w, 1) * scale, max(h, 1) * scale)

    # Denoise before enlargement when the source is compressed or soft.
    source_score = quality_score(rgb)
    if source_score["sharpness"] < 180:
        denoise_strength = 5 + round(strength * 4)
        rgb = cv2.fastNlMeansDenoisingColored(rgb, None, denoise_strength, 7, 21)

    # Edge-directed interpolation preserves cleaner boundaries than Lanczos alone.
    if scale <= 2:
        result = cv2.resize(rgb, target, interpolation=cv2.INTER_CUBIC)
    else:
        first = cv2.resize(rgb, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        result = cv2.resize(first, target, interpolation=cv2.INTER_LANCZOS4)

    lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.2 + strength * 0.8, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    gray = cv2.cvtColor(result, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.2)
    detail_mask = cv2.subtract(gray, blurred)

    edges = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    edge_weight = cv2.normalize(edges, None, 0, 1, cv2.NORM_MINMAX).astype(np.float32)
    edge_weight = cv2.GaussianBlur(edge_weight, (5, 5), 0)
    amount = 0.55 + strength * 0.95
    rgb_detail = cv2.cvtColor(detail_mask, cv2.COLOR_GRAY2RGB)
    weighted_detail = rgb_detail.astype(np.float32) * edge_weight[:, :, None]
    sharpened = result.astype(np.float32) + amount * weighted_detail
    return np.clip(sharpened, 0, 255).astype(np.uint8)


@app.post("/api/enhance")
async def enhance(
    file: UploadFile = File(...),
    scale: int = Form(2),
    strength: float = Form(0.75),
):
    if scale not in (2, 4):
        raise HTTPException(400, "Scale must be 2 or 4.")
    strength = max(0.0, min(1.0, strength))
    data = await file.read()
    if not data:
        raise HTTPException(400, "Please choose an image or video.")
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(413, "File must be 100 MB or smaller.")

    content_type = (file.content_type or "").lower()
    if content_type in IMAGE_TYPES:
        try:
            pil_image = Image.open(BytesIO(data))
            pil_image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(400, "Invalid image file.")
        if pil_image.format not in {"JPEG", "PNG", "WEBP"}:
            raise HTTPException(400, "Upload JPG, PNG or WEBP.")
        width, height = pil_image.size
        if width * height > 20_000_000:
            raise HTTPException(413, "Image dimensions are too large.")
        if width * scale > 8192 or height * scale > 8192:
            raise HTTPException(413, "The 4× result would exceed 8192 pixels.")

        rgb = np.array(pil_image.convert("RGB"))
        result = enhance_image(rgb, scale, strength)
        score = quality_score(rgb)

        name = f"{uuid4().hex}.png"
        ok, encoded = cv2.imencode(".png", cv2.cvtColor(result, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 4])
        if not ok:
            raise HTTPException(500, "Could not encode the enhanced image.")
        (OUTPUTS / name).write_bytes(encoded.tobytes())
        return Response(
            content=encoded.tobytes(),
            media_type="image/png",
            headers={
                "Content-Disposition": 'inline; filename="photorevive-enhanced.png"',
                "X-Original-Width": str(width),
                "X-Original-Height": str(height),
                "X-Enhanced-Width": str(width * scale),
                "X-Enhanced-Height": str(height * scale),
                "X-Source-Quality": str(score["estimated_quality"]),
                "X-Enhancement-Method": "Adaptive denoise, edge-aware detail and local contrast",
            },
        )

    if content_type in VIDEO_TYPES:
        source_name = f"source_{uuid4().hex}{Path(file.filename or 'video.mp4').suffix.lower()}"
        source_path = OUTPUTS / source_name
        source_path.write_bytes(data)
        name = f"{uuid4().hex}.mp4"
        output_path = OUTPUTS / name
        capture = cv2.VideoCapture(str(source_path))
        if not capture.isOpened():
            source_path.unlink(missing_ok=True)
            raise HTTPException(400, "Invalid or unsupported video file.")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        fps = min(max(float(fps), 1.0), 60.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps else 0
        if duration > 30:
            capture.release()
            source_path.unlink(missing_ok=True)
            raise HTTPException(413, "Video may be 30 seconds or shorter.")

        first_ok, first = capture.read()
        if not first_ok:
            capture.release()
            source_path.unlink(missing_ok=True)
            raise HTTPException(400, "Could not read video frames.")
        out_h, out_w = first.shape[0] * scale, first.shape[1] * scale
        if out_w > 3840 or out_h > 2160:
            capture.release()
            source_path.unlink(missing_ok=True)
            raise HTTPException(413, "Video output exceeds 4K resolution.")

        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
        if not writer.isOpened():
            capture.release()
            source_path.unlink(missing_ok=True)
            raise HTTPException(500, "This server cannot encode MP4 video.")

        processed = 0
        quality_sum = None
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = enhance_image(rgb, scale, strength)
            writer.write(cv2.cvtColor(result, cv2.COLOR_RGB2BGR))
            if processed % 30 == 0:
                scores = quality_score(rgb)
                quality_sum = scores if quality_sum is None else {
                    key: quality_sum[key] + scores[key] for key in quality_sum
                }
            processed += 1

        capture.release()
        writer.release()
        source_path.unlink(missing_ok=True)
        if processed == 0:
            output_path.unlink(missing_ok=True)
            raise HTTPException(400, "No readable video frames were found.")

        quality = None
        if quality_sum:
            samples = max(1, (processed + 29) // 30)
            quality = {key: round(value / samples) if key == "estimated_quality" else round(value / samples, 1) for key, value in quality_sum.items()}
        video_bytes = output_path.read_bytes()
        output_path.unlink(missing_ok=True)
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": 'inline; filename="photorevive-enhanced.mp4"',
                "X-Original-Width": str(int(first.shape[1])),
                "X-Original-Height": str(int(first.shape[0])),
                "X-Enhanced-Width": str(out_w),
                "X-Enhanced-Height": str(out_h),
                "X-Processed-FRAMES": str(processed),
                "X-Source-Quality": str(quality["estimated_quality"] if quality else ""),
            },
        )

    raise HTTPException(400, "Upload a JPG, PNG, WEBP, MP4, MOV or WEBM file.")
