const form = document.getElementById("playlist-form");
const input = document.getElementById("url");
const modeSelect = document.getElementById("mode");
const qualitySelect = document.getElementById("quality");
const filenameInput = document.getElementById("filename");
const downloadBtn = document.getElementById("download-btn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");

const AUDIO_QUALITIES = ["320", "128"];
const VIDEO_QUALITIES = ["1080", "720", "480", "360"];

const setStatus = (message, tone = "neutral") => {
  statusEl.textContent = message;
  statusEl.classList.remove("positive", "negative");
  if (tone === "positive") statusEl.classList.add("positive");
  if (tone === "negative") statusEl.classList.add("negative");
};

const setBusy = (isBusy, label = "Download playlist (ZIP)") => {
  downloadBtn.disabled = isBusy;
  downloadBtn.textContent = isBusy ? "Working..." : label;
};

const resetProgress = () => {
  progressWrap.hidden = true;
  progressBar.style.width = "0%";
};

const showProgress = () => {
  progressWrap.hidden = false;
  progressBar.style.width = "0%";
};

const populateQuality = () => {
  const mode = modeSelect.value;
  const items = mode === "audio" ? AUDIO_QUALITIES : VIDEO_QUALITIES;
  qualitySelect.innerHTML = "";
  items.forEach((q) => {
    const opt = document.createElement("option");
    opt.value = q;
    opt.textContent = mode === "audio" ? `${q} kbps` : `${q}p`;
    qualitySelect.append(opt);
  });
};

const extractFilename = (disposition, fallback) => {
  if (!disposition) return fallback;
  const match = /filename\*?=([^;]+)/i.exec(disposition);
  if (!match) return fallback;
  const value = match[1].trim().replace(/^UTF-8''/, "");
  return decodeURIComponent(value).replace(/["']/g, "") || fallback;
};

const buildPayload = () => {
  const mode = modeSelect.value;
  return {
    url: input.value.trim(),
    quality: qualitySelect.value,
    filename: filenameInput.value.trim(),
    container: mode === "audio" ? "mp3" : "mp4",
  };
};

const startDownload = async () => {
  const payload = buildPayload();
  if (!payload.url) {
    setStatus("Please paste a playlist URL first.", "negative");
    return;
  }

  setBusy(true);
  setStatus("Playlist download started...", "neutral");
  resetProgress();

  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const data = await response.json();
        if (data?.error) message = data.error;
      } catch (_) {
        const text = await response.text();
        message = text || message;
      }
      throw new Error(message);
    }

    setStatus("Zipping playlist on the server...", "neutral");
    showProgress();

    const contentLength = Number(response.headers.get("Content-Length")) || 0;
    const reader = response.body?.getReader ? response.body.getReader() : null;
    let blob;

    if (!reader) {
      blob = await response.blob();
    } else {
      const chunks = [];
      let received = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (contentLength > 0) {
          const percent = Math.min(100, Math.floor((received / contentLength) * 100));
          progressBar.style.width = `${percent}%`;
          setStatus(`Downloading... ${percent}%`, "neutral");
        }
      }
      blob = new Blob(chunks, { type: response.headers.get("Content-Type") || "application/octet-stream" });
    }

    const fallbackName = "playlist.zip";
    const filename = extractFilename(response.headers.get("Content-Disposition"), fallbackName);
    const blobUrl = window.URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    anchor.style.display = "none";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(blobUrl);

    setStatus("Download completed.", "positive");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Something went wrong. Please try again.", "negative");
  } finally {
    setBusy(false);
    resetProgress();
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await startDownload();
});

modeSelect.addEventListener("change", populateQuality);

populateQuality();
