import os
import yt_dlp

def download_video(url: str, output_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

    return {
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "source": info.get("extractor", "unknown"),
        "file_path": file_path,
    }
