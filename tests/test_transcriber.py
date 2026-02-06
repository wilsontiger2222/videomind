import pytest
from unittest.mock import patch, MagicMock, mock_open
from app.services.transcriber import transcribe_audio

@patch("builtins.open", mock_open(read_data=b"fake audio data"))
@patch("app.services.transcriber.openai.OpenAI")
def test_transcribe_returns_segments(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_segment_1 = MagicMock()
    mock_segment_1.start = 0.0
    mock_segment_1.end = 5.0
    mock_segment_1.text = "Hello world"

    mock_segment_2 = MagicMock()
    mock_segment_2.start = 5.0
    mock_segment_2.end = 10.0
    mock_segment_2.text = "This is a test"

    mock_response = MagicMock()
    mock_response.text = "Hello world This is a test"
    mock_response.segments = [mock_segment_1, mock_segment_2]

    mock_client.audio.transcriptions.create.return_value = mock_response

    result = transcribe_audio("/tmp/audio.wav")

    assert result["full_text"] == "Hello world This is a test"
    assert len(result["segments"]) == 2
    assert result["segments"][0]["text"] == "Hello world"
    assert result["segments"][0]["start"] == 0.0
