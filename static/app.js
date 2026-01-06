const form = document.getElementById("download-form");
const input = document.getElementById("url");
const button = document.getElementById("download-btn");
const statusEl = document.getElementById("status");

const setStatus = (message, tone = "neutral") => {
  statusEl.textContent = message;
  statusEl.classList.remove("positive", "negative");
  if (tone === "positive") statusEl.classList.add("positive");
  if (tone === "negative") statusEl.classList.add("negative");
};

const extractFilename = (disposition, fallback) => {
  if (!disposition) return fallback;
  const match = /filename\*?=([^;]+)/i.exec(disposition);
  if (!match) return fallback;
  const value = match[1].trim().replace(/^UTF-8''/, "");
  return decodeURIComponent(value).replace(/["']/g, "") || fallback;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = input.value.trim();
  if (!url) {
    setStatus("Please paste a YouTube URL first.", "negative");
    return;
  }

  button.disabled = true;
  button.textContent = "Working...";
  setStatus("Downloading and merging on the server. This can take a moment...");

  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
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

    setStatus("Download ready! Your video should start saving shortly.", "positive");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Something went wrong. Please try again.", "negative");
  } finally {
    button.disabled = false;
    button.textContent = "Download MP4";
  }
});
