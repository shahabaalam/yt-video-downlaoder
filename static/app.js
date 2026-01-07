const form = document.getElementById("download-form");
const input = document.getElementById("url");
const filenameInput = document.getElementById("filename");
const downloadBtn = document.getElementById("download-btn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");
const historyList = document.getElementById("history-list");
const refreshHistoryBtn = document.getElementById("refresh-history");
const resultCard = document.getElementById("result-card");
const audioRows = document.getElementById("audio-rows");
const videoRows = document.getElementById("video-rows");
const mediaThumb = document.getElementById("media-thumb");
const mediaTitle = document.getElementById("media-title");
const tabButtons = Array.from(document.querySelectorAll(".tab[data-tab]"));
const panels = {
  audio: document.getElementById("audio-panel"),
  video: document.getElementById("video-panel"),
};

let hasFormats = false;
let videoState = { qualities: [], containers: [] };
let audioState = { qualities: [] };
let mediaMeta = { title: "", thumbnail: "" };
const AUDIO_OPTIONS = ["320", "128"];

const setStatus = (message, tone = "neutral") => {
  statusEl.textContent = message;
  statusEl.classList.remove("positive", "negative");
  if (tone === "positive") statusEl.classList.add("positive");
  if (tone === "negative") statusEl.classList.add("negative");
};

const setBusy = (isBusy, label = "Fetch formats") => {
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

const buildPayload = (quality, container) => ({
  url: input.value.trim(),
  quality,
  filename: filenameInput.value.trim(),
  container,
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

const renderPreview = (meta = {}) => {
  mediaTitle.textContent = meta.title || "Ready to download";
  if (meta.thumbnail) {
    mediaThumb.src = meta.thumbnail;
    mediaThumb.alt = meta.title || "Video thumbnail";
    mediaThumb.hidden = false;
  } else {
    mediaThumb.src = "";
    mediaThumb.hidden = true;
  }
  resultCard.hidden = false;
};

const renderAudioRows = (qualities) => {
  audioRows.innerHTML = "";
  const list = qualities && qualities.length ? qualities : AUDIO_OPTIONS;
  list.forEach((q) => {
    const row = document.createElement("tr");
    const fileType = document.createElement("td");
    fileType.textContent = `MP3 - ${q}kbps`;

    const format = document.createElement("td");
    format.textContent = "Auto";

    const action = document.createElement("td");
    action.className = "action-cell";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "⬇ Download";
    btn.addEventListener("click", () => startDownload(q, "mp3"));
    action.append(btn);

    row.append(fileType, format, action);
    audioRows.append(row);
  });
};

const renderVideoRows = (qualities, containers) => {
  videoRows.innerHTML = "";
  const list = qualities && qualities.length ? qualities : [];
  const videoContainers = (containers || []).filter((c) => c !== "m4a" && c !== "mp3");
  list.forEach((quality) => {
    videoContainers.forEach((container) => {
      const row = document.createElement("tr");

      const fileType = document.createElement("td");
      fileType.textContent = `${container.toUpperCase()} - ${quality}`;

      const format = document.createElement("td");
      format.textContent = container.toUpperCase();

      const action = document.createElement("td");
      action.className = "action-cell";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "⬇ Download";
      btn.addEventListener("click", () => startDownload(quality, container));
      action.append(btn);

      row.append(fileType, format, action);
      videoRows.append(row);
    });
  });
};

const applyTab = (tab) => {
  tabButtons.forEach((btn) => {
    const isActive = btn.dataset.tab === tab;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  Object.entries(panels).forEach(([key, panel]) => {
    panel.hidden = key !== tab;
  });
};

const populateFormats = (videoResp, audioResp) => {
  videoState = {
    qualities: videoResp?.qualities || [],
    containers: videoResp?.containers || [],
  };
  audioState = { qualities: AUDIO_OPTIONS };
  mediaMeta = videoResp?.meta || audioResp?.meta || { title: "", thumbnail: "" };

  renderPreview(mediaMeta);
  renderAudioRows(audioState.qualities);
  renderVideoRows(videoState.qualities, videoState.containers);
  applyTab("audio");
  hasFormats = true;
  setStatus("Formats loaded. Pick Audio or Video and click Download.", "positive");
};

const fetchAllFormats = async (url) => {
  setBusy(true, "Fetching...");
  setStatus("Fetching available formats...", "neutral");
  try {
    const [videoRes, audioRes] = await Promise.all([
      fetch("/api/formats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),
      fetch("/api/audio-formats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),
    ]);

    const videoData = videoRes.ok ? await videoRes.json() : null;
    const audioData = audioRes.ok ? await audioRes.json() : null;

    if (!videoRes.ok) {
      throw new Error(videoData?.error || `Video formats failed (${videoRes.status})`);
    }
    if (!audioRes.ok) {
      throw new Error(audioData?.error || `Audio formats failed (${audioRes.status})`);
    }

    populateFormats(videoData, audioData);
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Unable to fetch formats.", "negative");
  } finally {
    setBusy(false, "Fetch formats");
  }
};

const startDownload = async (quality, container) => {
  const payload = buildPayload(quality, container);
  if (!payload.url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }

  setBusy(true, "Downloading...");
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

    const fallbackName = container === "mp3" ? "audio.mp3" : "video.mp4";
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
    fetchHistory();
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Something went wrong. Please try again.", "negative");
  } finally {
    setBusy(false, "Fetch formats");
    resetProgress();
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = input.value.trim();
  if (!url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }
  await fetchAllFormats(url);
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => applyTab(btn.dataset.tab));
});

refreshHistoryBtn.addEventListener("click", fetchHistory);

// Initial load
fetchHistory();
