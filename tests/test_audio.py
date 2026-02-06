import os
import pytest
from unittest.mock import patch
from app.services.audio import extract_audio

@patch("app.services.audio.subprocess.run")
def test_extract_audio_creates_wav(mock_run):
    mock_run.return_value = None

    result = extract_audio("/tmp/video.mp4", "/tmp")

    expected = os.path.join("/tmp", "video.wav")
    assert result == expected
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "ffmpeg" in call_args[0]
    assert "/tmp/video.mp4" in call_args

@patch("app.services.audio.subprocess.run")
def test_extract_audio_ffmpeg_fails(mock_run):
    mock_run.side_effect = Exception("FFmpeg not found")

    with pytest.raises(Exception, match="FFmpeg not found"):
        extract_audio("/tmp/video.mp4", "/tmp")
