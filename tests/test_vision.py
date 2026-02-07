# tests/test_vision.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
from app.services.vision import analyze_frame, analyze_frames
import base64


@patch("builtins.open", mock_open(read_data=b"fake image data"))
@patch("app.services.vision.openai.OpenAI")
def test_analyze_frame_returns_description(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = "A terminal window showing Docker commands"

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = analyze_frame("/tmp/frame_0001.jpg")

    assert result == "A terminal window showing Docker commands"
    mock_client.chat.completions.create.assert_called_once()


@patch("app.services.vision.analyze_frame")
def test_analyze_frames_processes_all(mock_analyze):
    mock_analyze.side_effect = ["Description 1", "Description 2"]

    frames = [
        {"path": "/tmp/frame_0001.jpg", "timestamp": 5.0},
        {"path": "/tmp/frame_0002.jpg", "timestamp": 10.0},
    ]

    result = analyze_frames(frames)

    assert len(result) == 2
    assert result[0]["description"] == "Description 1"
    assert result[0]["timestamp"] == 5.0
    assert result[1]["description"] == "Description 2"
    assert result[1]["timestamp"] == 10.0


@patch("app.services.vision.analyze_frame")
def test_analyze_frames_handles_failure_gracefully(mock_analyze):
    mock_analyze.side_effect = [Exception("API error"), "Description 2"]

    frames = [
        {"path": "/tmp/frame_0001.jpg", "timestamp": 5.0},
        {"path": "/tmp/frame_0002.jpg", "timestamp": 10.0},
    ]

    result = analyze_frames(frames)

    assert len(result) == 2
    assert result[0]["description"] == "Analysis failed"
    assert result[1]["description"] == "Description 2"
