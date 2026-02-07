# app/services/frames.py
import os
import posixpath
import subprocess
from PIL import Image
import imagehash


def extract_frames(video_path: str, output_dir: str, interval: int = 5) -> list:
    """Extract one frame every `interval` seconds from a video using FFmpeg."""
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            "-y",
            os.path.join(output_dir, "frame_%04d.jpg")
        ],
        check=True,
        capture_output=True
    )

    frame_files = sorted(
        f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    return [posixpath.join(output_dir, f) for f in frame_files]


def deduplicate_frames(frame_paths: list, threshold: int = 5) -> list:
    """Remove near-duplicate frames using perceptual hashing."""
    if not frame_paths:
        return []

    kept = [frame_paths[0]]
    last_hash = imagehash.average_hash(Image.open(frame_paths[0]))

    for path in frame_paths[1:]:
        current_hash = imagehash.average_hash(Image.open(path))
        diff = last_hash - current_hash
        if diff > threshold:
            kept.append(path)
            last_hash = current_hash

    return kept
