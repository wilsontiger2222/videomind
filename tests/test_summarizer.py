import pytest
from unittest.mock import patch, MagicMock
from app.services.summarizer import summarize_transcript

@patch("app.services.summarizer.openai.OpenAI")
def test_summarize_returns_short_and_detailed(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"short": "A tutorial about Docker.", "detailed": "This video covers Docker installation, basic commands, and deployment.", "chapters": [{"start": "0:00", "end": "5:00", "title": "Introduction"}]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = summarize_transcript("This is a transcript about Docker...")

    assert result["short"] == "A tutorial about Docker."
    assert "Docker" in result["detailed"]
    assert len(result["chapters"]) == 1
