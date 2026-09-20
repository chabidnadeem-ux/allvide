from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import tempfile

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "VideoSave Backend Running",
        "version": "2.0"
    })


@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        fmt = data.get("format", "auto").lower()

        if not url:
            return jsonify({"error": "URL is required"}), 400

        # MP3
        if fmt == "mp3":
            ydl_opts = {
                "format": "ba/b",
                "outtmpl": os.path.join(
                    "%(tmpdir)s", "%(title)s.%(ext)s"
                ),
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

        # MP4 / Auto
        else:
            ydl_opts = {
                # Flexible format selection.
                # Do NOT force mp4-only formats.
                "format": "bv*+ba/b",
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }

        with tempfile.TemporaryDirectory() as tmpdir:

            ydl_opts["outtmpl"] = os.path.join(
                tmpdir, "%(title)s.%(ext)s"
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                title = info.get("title") or "video"

                # Find downloaded file
                files = [
                    os.path.join(tmpdir, f)
                    for f in os.listdir(tmpdir)
                    if os.path.isfile(os.path.join(tmpdir, f))
                ]

                if not files:
                    return jsonify({
                        "error": "No downloaded file was created."
                    }), 500

                # Prefer requested extension
                actual_file = None

                if fmt == "mp3":
                    for f in files:
                        if f.lower().endswith(".mp3"):
                            actual_file = f
                            break
                else:
                    for f in files:
                        if f.lower().endswith(".mp4"):
                            actual_file = f
                            break

                if actual_file is None:
                    actual_file = files[0]

                extension = os.path.splitext(actual_file)[1].lower()

                if extension == ".mp3":
                    mime = "audio/mpeg"
                elif extension == ".mp4":
                    mime = "video/mp4"
                elif extension == ".webm":
                    mime = "video/webm"
                elif extension == ".m4a":
                    mime = "audio/mp4"
                else:
                    mime = "application/octet-stream"

                safe_title = "".join(
                    c for c in title
                    if c.isalnum() or c in (" ", "-", "_")
                ).strip()

                if not safe_title:
                    safe_title = "VideoSave"

                filename = safe_title + extension

                file_size = os.path.getsize(actual_file)

                def generate():
                    with open(actual_file, "rb") as file:
                        while True:
                            chunk = file.read(1024 * 1024)
                            if not chunk:
                                break
                            yield chunk

                return Response(
                    generate(),
                    mimetype=mime,
                    headers={
                        "Content-Disposition":
                            f'attachment; filename="{filename}"',
                        "Content-Length": str(file_size),
                        "Access-Control-Allow-Origin": "*",
                    },
                )

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
