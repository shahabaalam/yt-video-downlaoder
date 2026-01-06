import os
import shutil
from typing import Any, Dict

from flask import (
    Flask,
    after_this_request,
    jsonify,
    request,
    send_file,
)

from downloader import DownloadError, download_video

app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index() -> Any:
    return app.send_static_file("index.html")


@app.post("/api/download")
def handle_download() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    url = payload.get("url") or request.form.get("url")

    if not url:
        return jsonify({"error": "Please provide a YouTube URL."}), 400

    try:
        file_path, temp_dir = download_video(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except DownloadError as exc:
        return jsonify({"error": str(exc)}), 500

    filename = os.path.basename(file_path)

    @after_this_request
    def cleanup(response: Any) -> Any:
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
        return response

    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
