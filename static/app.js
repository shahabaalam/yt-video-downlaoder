const form = document.getElementById("download-form");
const urlInput = document.getElementById("url");
const qualitySelect = document.getElementById("quality");
const submitBtn = document.getElementById("submit");
const statusLabel = document.getElementById("status-label");
const percentLabel = document.getElementById("percent");
const progressFill = document.getElementById("progress-fill");
const alertBox = document.getElementById("alert");
const downloadLinkWrap = document.getElementById("download-link");
const downloadAnchor = document.getElementById("link");

let pollTimer = null;
let currentJob = null;

function setStatus(message, progressValue = null) {
  statusLabel.textContent = message;
  if (progressValue !== null) {
    const clamped = Math.max(0, Math.min(100, progressValue));
    percentLabel.textContent = `${clamped.toFixed(0)}%`;
    progressFill.style.width = `${clamped}%`;
  }
}

function setAlert(message, isError = true) {
  if (!message) {
    alertBox.classList.add("hidden");
    alertBox.textContent = "";
    return;
  }
  alertBox.textContent = message;
  alertBox.classList.toggle("error", isError);
  alertBox.classList.toggle("success", !isError);
  alertBox.classList.remove("hidden");
}

async function startDownload(event) {
  event.preventDefault();
  if (pollTimer) clearInterval(pollTimer);
  setAlert("");
  downloadLinkWrap.classList.add("hidden");
  submitBtn.disabled = true;
  setStatus("Starting...", 0);

  const payload = {
    url: urlInput.value.trim(),
    quality: qualitySelect.value,
  };

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || "Failed to start download");
    }

    const data = await res.json();
    currentJob = data.job_id;
    pollTimer = setInterval(() => checkStatus(currentJob), 1400);
  } catch (err) {
    setAlert(err.message || "Unable to start download");
    submitBtn.disabled = false;
    setStatus("Idle", 0);
  }
}

async function checkStatus(jobId) {
  try {
    const res = await fetch(`/api/status/${jobId}`);
    if (!res.ok) {
      throw new Error("Status request failed");
    }
    const data = await res.json();
    const { status, progress, download_url: downloadUrl, error, filename } = data;

    if (status === "downloading") {
      setStatus("Downloading...", progress ?? 0);
    } else if (status === "merging") {
      setStatus("Merging audio and video...", progress ?? 99);
    } else if (status === "completed") {
      setStatus("Ready", 100);
      clearInterval(pollTimer);
      pollTimer = null;
      submitBtn.disabled = false;
      if (downloadUrl) {
        downloadAnchor.href = downloadUrl;
        downloadAnchor.textContent = `Download ${filename || "file"}`;
        downloadLinkWrap.classList.remove("hidden");
      }
      setAlert("Download complete", false);
    } else if (status === "queued") {
      setStatus("Queued...", progress ?? 0);
    } else if (status === "error") {
      clearInterval(pollTimer);
      pollTimer = null;
      submitBtn.disabled = false;
      setStatus("Error", progress ?? 0);
      setAlert(error || "Download failed");
    } else {
      setStatus("Idle", progress ?? 0);
    }
  } catch (err) {
    clearInterval(pollTimer);
    pollTimer = null;
    submitBtn.disabled = false;
    setStatus("Error", 0);
    setAlert(err.message || "Unable to fetch status");
  }
}

form.addEventListener("submit", startDownload);
