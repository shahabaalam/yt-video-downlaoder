const form = document.getElementById("download-form");
const input = document.getElementById("url");
const qualitySelect = document.getElementById("audio-quality");
const filenameInput = document.getElementById("filename");
const downloadBtn = document.getElementById("download-btn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");
const historyList = document.getElementById("history-list");
const refreshHistoryBtn = document.getElementById("refresh-history");
const optionsBlock = document.getElementById("options");

let hasOptions = false;

const setStatus = (message, tone = "neutral") => {
  statusEl.textContent = message;
  statusEl.classList.remove("positive", "negative");
  if (tone === "positive") statusEl.classList.add("positive");
  if (tone === "negative") statusEl.classList.add("negative");
};

const setBusy = (isBusy, label = "Download audio") => {
  downloadBtn.disabled = isBusy;
  downloadBtn.textContent = isBusy ? "Working..." : label;
};

const extractFilename = (disposition, fallback) => {
  if (!disposition) return fallback;
  const match = /filename\*?=([^;]+)/i.exec(disposition);
  if (!match) return fallback;
  const value = match[1].trim().replace(/^UTF-8''/, "");
  return decodeURIComponent(value).replace(/["']/g, "") || fallback;
};

const buildPayload = () => ({
  url: input.value.trim(),
  quality: qualitySelect.value || "192",
  filename: filenameInput.value.trim(),
  container: "m4a",
});

const resetProgress = () => {
  progressWrap.hidden = true;
  progressBar.style.width = "0%";
};

const showProgress = () => {
  progressWrap.hidden = false;
  progressBar.style.width = "0%";
};

const renderHistory = (items) => {
  historyList.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "No downloads yet.";
    historyList.append(li);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");

    const left = document.createElement("div");
    const chip = document.createElement("span");
    chip.className = "chip";
    const containerLabel = item.container ? ` ${item.container.toUpperCase()}` : "";
    chip.textContent = `${item.quality}${containerLabel}`;

    const title = document.createElement("div");
    title.innerHTML = `<strong>${item.filename}</strong>`;

    const meta = document.createElement("div");
    const date = new Date(item.timestamp * 1000).toLocaleString();
    meta.className = "muted";
    meta.textContent = `${item.mode} - ${date}`;

    left.append(chip, title, meta);
    li.append(left);
    historyList.append(li);
  });
};

const fetchHistory = async () => {
  try {
    const res = await fetch("/api/history");
    if (!res.ok) throw new Error(`History failed (${res.status})`);
    const data = await res.json();
    renderHistory(data.items || []);
  } catch (error) {
    console.error(error);
    setStatus("Could not load history.", "negative");
  }
};

const populateOptions = (qualities) => {
  qualitySelect.innerHTML = "";
  (qualities || []).forEach((q) => {
    const option = document.createElement("option");
    option.value = q;
    option.textContent = `${q} kbps`;
    qualitySelect.append(option);
  });
  optionsBlock.hidden = false;
  hasOptions = true;
  downloadBtn.textContent = "Download audio";
};

const fetchAudioFormats = async (payload) => {
  setStatus("Fetching available audio qualities...", "neutral");
  setBusy(true, "Fetch audio qualities");
  try {
    const res = await fetch("/api/audio-formats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: payload.url }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `Formats failed (${res.status})`);
    }
    const data = await res.json();
    populateOptions(data.qualities);
    setStatus("Audio qualities loaded. Choose one, then Download.", "positive");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Unable to fetch audio qualities.", "negative");
  } finally {
    setBusy(false, hasOptions ? "Download audio" : "Fetch audio qualities");
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = buildPayload();
  if (!payload.url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }

  if (!hasOptions) {
    await fetchAudioFormats(payload);
    return;
  }

  setBusy(true);
  setStatus("Download started...", "neutral");
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

    setStatus("Download merging on the server...", "neutral");
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

    const filename = extractFilename(response.headers.get("Content-Disposition"), "audio.m4a");
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
    fetchHistory();
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Something went wrong. Please try again.", "negative");
  } finally {
    setBusy(false, "Download audio");
    resetProgress();
  }
});

refreshHistoryBtn.addEventListener("click", fetchHistory);

// Initial load
fetchHistory();
