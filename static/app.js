const form = document.getElementById("download-form");
const input = document.getElementById("url");
const qualitySelect = document.getElementById("quality");
const filenameInput = document.getElementById("filename");
const downloadBtn = document.getElementById("download-btn");
const linkBtn = document.getElementById("link-btn");
const statusEl = document.getElementById("status");
const historyList = document.getElementById("history-list");
const refreshHistoryBtn = document.getElementById("refresh-history");

const setStatus = (message, tone = "neutral") => {
  statusEl.textContent = message;
  statusEl.classList.remove("positive", "negative");
  if (tone === "positive") statusEl.classList.add("positive");
  if (tone === "negative") statusEl.classList.add("negative");
};

const setBusy = (isBusy, label = "Download") => {
  downloadBtn.disabled = isBusy;
  linkBtn.disabled = isBusy;
  if (isBusy) {
    downloadBtn.textContent = "Working...";
  } else {
    downloadBtn.textContent = label;
  }
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
  quality: qualitySelect.value,
  filename: filenameInput.value.trim(),
});

const copyToClipboard = async (text) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const temp = document.createElement("textarea");
  temp.value = text;
  temp.style.position = "fixed";
  temp.style.opacity = "0";
  document.body.append(temp);
  temp.select();
  const success = document.execCommand("copy");
  temp.remove();
  return success;
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
    chip.textContent = item.quality;

    const title = document.createElement("div");
    title.innerHTML = `<strong>${item.filename}</strong>`;

    const meta = document.createElement("div");
    const date = new Date(item.timestamp * 1000).toLocaleString();
    meta.className = "muted";
    meta.textContent = `${item.mode} - ${date}`;

    left.append(chip, title, meta);

    const actions = document.createElement("div");
    actions.className = "history-actions";
    if (item.link) {
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "secondary copy-btn";
      copyBtn.textContent = "Copy link";
      copyBtn.addEventListener("click", async () => {
        const absoluteLink = new URL(item.link, window.location.origin).toString();
        try {
          await copyToClipboard(absoluteLink);
          setStatus("Link copied.", "positive");
        } catch (error) {
          console.error(error);
          setStatus("Unable to copy link.", "negative");
        }
      });
      actions.append(copyBtn);
    }

    li.append(left, actions);
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = buildPayload();
  if (!payload.url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }

  setBusy(true);
  setStatus("Download started...", "neutral");

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

    const blob = await response.blob();
    const filename = extractFilename(response.headers.get("Content-Disposition"), "video.mp4");
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
    setBusy(false, "Download");
  }
});

linkBtn.addEventListener("click", async () => {
  const payload = buildPayload();
  if (!payload.url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }

  setBusy(true);
  setStatus("Preparing link...", "neutral");

  try {
    const response = await fetch("/api/link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `Request failed (${response.status})`);
    }

    const data = await response.json();
    const absoluteLink = new URL(data.link, window.location.origin).toString();
    await copyToClipboard(absoluteLink);

    setStatus("Download link copied to clipboard.", "positive");
    fetchHistory();
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Unable to create download link.", "negative");
  } finally {
    setBusy(false, "Download");
  }
});

refreshHistoryBtn.addEventListener("click", fetchHistory);

// Initial load
fetchHistory();
