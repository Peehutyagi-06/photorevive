const fileInput = document.getElementById("file");
const choose = document.getElementById("choose");
const preview = document.getElementById("preview");
const original = document.getElementById("original");
const videoPreview = document.getElementById("video-preview");
const previewTitle = document.getElementById("preview-title");
const filename = document.getElementById("filename");
const status = document.getElementById("status");
const result = document.getElementById("result");
const enhance = document.getElementById("enhance");
const scale = document.getElementById("scale");
const strength = document.getElementById("strength");
let selected = null;
let previewURL = null;

choose.onclick = () => fileInput.click();

scale.onchange = () => {
  enhance.textContent = `Enhance ${scale.value}×`;
};

fileInput.onchange = () => {
  const file = fileInput.files[0];
  if (!file) return;
  const allowed = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime", "video/x-m4v", "video/webm"];
  if (!allowed.includes(file.type)) {
    status.textContent = "Choose a JPG, PNG, WEBP, MP4, MOV or WEBM file.";
    return;
  }
  if (file.size > 100 * 1024 * 1024) {
    status.textContent = "File must be 100 MB or smaller.";
    return;
  }

  selected = file;
  if (previewURL) URL.revokeObjectURL(previewURL);
  previewURL = URL.createObjectURL(file);
  const isVideo = file.type.startsWith("video/");
  original.hidden = isVideo;
  videoPreview.hidden = !isVideo;
  previewTitle.textContent = isVideo ? "Your original video" : "Your original image";
  if (isVideo) {
    videoPreview.src = previewURL;
  } else {
    original.src = previewURL;
  }
  filename.textContent = file.name;
  preview.hidden = false;
  result.hidden = true;
  status.textContent = isVideo ? "Videos are processed locally, frame by frame." : "";
};

enhance.onclick = async () => {
  if (!selected) return;
  const body = new FormData();
  body.append("file", selected);
  body.append("scale", scale.value);
  body.append("strength", String(Number(strength.value) / 100));
  enhance.disabled = true;
  enhance.textContent = "Restoring…";
  status.textContent = selected.type.startsWith("video/")
    ? "Processing video frames. This may take a moment…"
    : "Analyzing and restoring image…";

  try {
    const response = await fetch("/api/enhance", { method: "POST", body });
    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
      let message = "Could not process file.";
      if (contentType.includes("application/json")) {
        const error = await response.json();
        message = error.detail || message;
      } else {
        message = await response.text() || message;
      }
      throw new Error(message);
    }

    if (selected.type.startsWith("image/") && contentType.includes("image/png")) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const output = document.getElementById("output");
      if (output.tagName !== "IMG") output.outerHTML = '<img id="output" alt="Enhanced result">';
      document.getElementById("output").src = url;
      document.getElementById("download").href = url;
      document.getElementById("download").download = "photorevive-enhanced.png";

      const originalWidth = response.headers.get("X-Original-Width") || "";
      const originalHeight = response.headers.get("X-Original-Height") || "";
      const enhancedWidth = response.headers.get("X-Enhanced-Width") || "";
      const enhancedHeight = response.headers.get("X-Enhanced-Height") || "";
      const quality = response.headers.get("X-Source-Quality") || "";
      document.getElementById("dimensions").textContent =
        `Original: ${originalWidth} × ${originalHeight} | Enhanced: ${enhancedWidth} × ${enhancedHeight}`;
      document.getElementById("quality").textContent = quality ? `Estimated source quality: ${quality}/100` : "";
      document.getElementById("method").textContent =
        response.headers.get("X-Enhancement-Method") || "Adaptive image enhancement";
      result.hidden = false;
      status.textContent = "Your enhanced image is ready.";
      result.scrollIntoView({ behavior: "smooth" });
      return;
    }

    if (selected.type.startsWith("video/") && contentType.includes("video/mp4")) {
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      document.getElementById("output").outerHTML = '<video id="output" controls></video>';
      document.getElementById("output").src = url;
      document.getElementById("download").href = url;
      document.getElementById("download").download = "photorevive-enhanced.mp4";

      const originalWidth = response.headers.get("X-Original-Width") || "";
      const originalHeight = response.headers.get("X-Original-Height") || "";
      const enhancedWidth = response.headers.get("X-Enhanced-Width") || "";
      const enhancedHeight = response.headers.get("X-Enhanced-Height") || "";
      const frames = response.headers.get("X-Processed-FRAMES") || "";
      const quality = response.headers.get("X-Source-Quality") || "";
      document.getElementById("dimensions").textContent =
        `Original: ${originalWidth} × ${originalHeight} | Enhanced: ${enhancedWidth} × ${enhancedHeight} | Frames: ${frames}`;
      document.getElementById("quality").textContent = quality ? `Estimated source quality: ${quality}/100` : "";
      document.getElementById("method").textContent = "Adaptive per-frame denoise, edge detail and local contrast";
      result.hidden = false;
      status.textContent = "Your enhanced video is ready.";
      result.scrollIntoView({ behavior: "smooth" });
      return;
    }

    const data = await response.json();
    const url = data.download_url + "?v=" + Date.now();
    const output = document.getElementById("output");
    if (data.kind === "video") {
      output.outerHTML = '<video id="output" controls></video>';
      document.getElementById("output").src = url;
      document.getElementById("download").download = "photorevive-enhanced.mp4";
    } else {
      document.querySelectorAll("#output").forEach((element) => {
        if (element.tagName !== "IMG") {
          element.outerHTML = '<img id="output" alt="Enhanced result">';
        }
      });
      document.getElementById("output").src = url;
      document.getElementById("download").download = "photorevive-enhanced.png";
    }

    document.getElementById("download").href = data.download_url;
    const frameText = data.processed_frames ? ` | Frames: ${data.processed_frames}` : "";
    document.getElementById("dimensions").textContent =
      `Original: ${data.original_width} × ${data.original_height} | Enhanced: ${data.enhanced_width} × ${data.enhanced_height}${frameText}`;
    document.getElementById("method").textContent = data.method;
    if (data.quality) {
      const quality = data.quality;
      document.getElementById("quality").textContent =
        `Estimated source quality: ${quality.estimated_quality}/100`;
    } else {
      document.getElementById("quality").textContent = "";
    }

    result.hidden = false;
    status.textContent = "Your enhanced file is ready.";
    result.scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    status.textContent = error.message;
  } finally {
    enhance.disabled = false;
    enhance.textContent = `Enhance ${scale.value}×`;
  }
};
