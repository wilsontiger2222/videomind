import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.downloader import download_video

@patch("app.services.downloader.yt_dlp.YoutubeDL")
def test_download_video_returns_metadata(mock_ytdl_class):
    mock_ytdl = MagicMock()
    mock_ytdl_class.return_value.__enter__ = MagicMock(return_value=mock_ytdl)
    mock_ytdl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ytdl.extract_info.return_value = {
        "title": "Test Video",
        "duration": 120,
        "webpage_url": "https://youtube.com/watch?v=test",
        "extractor": "youtube",
    }
    mock_ytdl.prepare_filename.return_value = "/tmp/test_video.mp4"

    result = download_video("https://youtube.com/watch?v=test", output_dir="/tmp")

    assert result["title"] == "Test Video"
    assert result["duration"] == 120
    assert result["file_path"] == "/tmp/test_video.mp4"

@patch("app.services.downloader.yt_dlp.YoutubeDL")
def test_download_video_invalid_url(mock_ytdl_class):
    mock_ytdl = MagicMock()
    mock_ytdl_class.return_value.__enter__ = MagicMock(return_value=mock_ytdl)
    mock_ytdl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ytdl.extract_info.side_effect = Exception("Unsupported URL")

    with pytest.raises(Exception, match="Unsupported URL"):
        download_video("https://invalid-url.com", output_dir="/tmp")
