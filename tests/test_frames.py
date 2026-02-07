# tests/test_frames.py
import os
import pytest
from unittest.mock import patch, MagicMock, call
from app.services.frames import extract_frames, deduplicate_frames


@patch("app.services.frames.subprocess.run")
@patch("app.services.frames.os.listdir")
def test_extract_frames_calls_ffmpeg(mock_listdir, mock_run):
    mock_listdir.return_value = ["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"]
    mock_run.return_value = None

    result = extract_frames("/tmp/video.mp4", "/tmp/frames", interval=5)

    assert result == [
        "/tmp/frames/frame_0001.jpg",
        "/tmp/frames/frame_0002.jpg",
        "/tmp/frames/frame_0003.jpg",
    ]
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "ffmpeg" in cmd[0]
    assert "/tmp/video.mp4" in cmd


@patch("app.services.frames.imagehash.average_hash")
@patch("app.services.frames.Image.open")
def test_deduplicate_frames_removes_similar(mock_open, mock_hash):
    hash_a = MagicMock()
    hash_b = MagicMock()
    hash_c = MagicMock()

    hash_a.__sub__ = MagicMock(return_value=0)
    hash_b.__sub__ = MagicMock(return_value=0)
    hash_c.__sub__ = MagicMock(return_value=20)

    mock_hash.side_effect = [hash_a, hash_b, hash_c]

    hash_a.__sub__ = MagicMock(side_effect=lambda other: 0 if other is hash_b else 20)

    frames = ["/tmp/frame1.jpg", "/tmp/frame2.jpg", "/tmp/frame3.jpg"]
    result = deduplicate_frames(frames, threshold=5)

    assert len(result) == 2
    assert "/tmp/frame1.jpg" in result
    assert "/tmp/frame3.jpg" in result


@patch("app.services.frames.imagehash.average_hash")
@patch("app.services.frames.Image.open")
def test_deduplicate_frames_keeps_all_when_different(mock_open, mock_hash):
    hash_a = MagicMock()
    hash_b = MagicMock()

    mock_hash.side_effect = [hash_a, hash_b]
    hash_a.__sub__ = MagicMock(return_value=15)

    frames = ["/tmp/frame1.jpg", "/tmp/frame2.jpg"]
    result = deduplicate_frames(frames, threshold=5)

    assert len(result) == 2
