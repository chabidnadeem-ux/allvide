from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import threading
import time

app = Flask(__name__)
CORS(app)  # Allow all origins

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "VideoSave Backend Running", "version": "1.0"})

@app.route('/info', methods=['POST'])
def get_info():
    """Get video info without downloading"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        if not url:
            return jsonify({"error": "URL is required"}), 400

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in (info.get('formats') or []):
                if f.get('url') and f.get('ext') in ['mp4', 'webm', 'mp3', 'm4a']:
                    formats.append({
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'quality': f.get('quality'),
                        'height': f.get('height'),
                        'filesize': f.get('filesize'),
                        'url': f.get('url'),
                        'acodec': f.get('acodec'),
                        'vcodec': f.get('vcodec'),
                    })

            return jsonify({
                "title": info.get('title', 'video'),
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader'),
                "formats": formats[-10:],  # last 10 formats
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download', methods=['POST'])
def download_video():
    """Download and stream video directly"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        fmt = data.get('format', 'auto')  # auto, mp4, mp3

        if not url:
            return jsonify({"error": "URL is required"}), 400

        # Build yt-dlp options
        if fmt == 'mp3':
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': '%(title)s.%(ext)s',
            }
        elif fmt == 'mp4':
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'outtmpl': '%(title)s.%(ext)s',
            }
        else:  # auto
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'outtmpl': '%(title)s.%(ext)s',
                'merge_output_format': 'mp4',
            }

        # Use temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts['outtmpl'] = os.path.join(tmpdir, '%(title)s.%(ext)s')

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                # Sanitize filename
                filename = ydl.prepare_filename(info)
                # For MP3, extension changes
                if fmt == 'mp3':
                    filename = os.path.splitext(filename)[0] + '.mp3'

                # Find the actual file
                actual_file = None
                for f in os.listdir(tmpdir):
                    actual_file = os.path.join(tmpdir, f)
                    break

                if not actual_file or not os.path.exists(actual_file):
                    return jsonify({"error": "Download failed"}), 500

                ext = os.path.splitext(actual_file)[1].lower()
                mime = 'video/mp4' if ext == '.mp4' else ('audio/mpeg' if ext == '.mp3' else 'video/webm')
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_filename = f"{safe_title}{ext}"

                def generate():
                    with open(actual_file, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            yield chunk

                response = Response(
                    generate(),
                    mimetype=mime,
                    headers={
                        'Content-Disposition': f'attachment; filename="{safe_filename}"',
                        'Content-Length': str(os.path.getsize(actual_file)),
                        'Access-Control-Allow-Origin': '*',
                    }
                )
                return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/link', methods=['POST'])
def get_link():
    """Get direct download link (faster, no re-encoding)"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        fmt = data.get('format', 'auto')

        if not url:
            return jsonify({"error": "URL is required"}), 400

        if fmt == 'mp3':
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
        elif fmt == 'mp4':
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
        else:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            direct_url = info.get('url') or info.get('manifest_url')
            ext = info.get('ext', 'mp4')

            if not direct_url:
                # Try formats list
                formats = info.get('formats', [])
                if formats:
                    best = formats[-1]
                    direct_url = best.get('url')
                    ext = best.get('ext', 'mp4')

            if not direct_url:
                return jsonify({"error": "Could not extract direct link"}), 500

            return jsonify({
                "url": direct_url,
                "title": title,
                "ext": ext,
                "filename": f"{title}.{ext}",
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
