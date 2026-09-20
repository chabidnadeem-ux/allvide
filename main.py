from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import os
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "VideoSave Backend Running",
        "version": "3.0"
    })


@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json(silent=True) or {}

        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "error": "URL is required"
            }), 400

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return jsonify({
                "error": "Invalid URL"
            }), 400

        # Direct/public media URL only
        response = requests.get(
            url,
            stream=True,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        content_type = (
            response.headers.get(
                "Content-Type",
                "application/octet-stream"
            )
            .split(";")[0]
            .lower()
        )

        allowed_types = (
            "video/",
            "audio/"
        )

        if not content_type.startswith(allowed_types):
            return jsonify({
                "error": "This URL is not a direct audio/video file."
            }), 400

        filename = os.path.basename(parsed.path)

        if not filename:
            if content_type.startswith("audio/"):
                filename = "VideoSave.mp3"
            else:
                filename = "VideoSave.mp4"

        return Response(
            response.iter_content(chunk_size=1024 * 1024),
            content_type=content_type,
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}"',
                "Access-Control-Allow-Origin": "*"
            }
        )

    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": f"Download failed: {str(e)}"
        }), 500

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
