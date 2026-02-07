# tests/test_blog_writer.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.blog_writer import generate_blog


@patch("app.services.blog_writer.openai.OpenAI")
def test_generate_blog_returns_markdown(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"title": "Docker Tutorial: A Complete Guide", "content_markdown": "# Docker Tutorial\\n\\n## Introduction\\n\\nThis tutorial covers Docker basics.", "image_suggestions": [{"timestamp": 5.0, "caption": "Docker architecture", "insert_after": "## Architecture"}]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = generate_blog(
        transcript="This is a Docker tutorial...",
        summary="A Docker tutorial covering basics.",
        chapters=[{"start": "0:00", "end": "5:00", "title": "Introduction"}],
        visual_analysis=[{"timestamp": 5.0, "description": "Architecture diagram"}],
        style="tutorial"
    )

    assert result["title"] == "Docker Tutorial: A Complete Guide"
    assert "# Docker Tutorial" in result["content_markdown"]
    assert len(result["image_suggestions"]) == 1


@patch("app.services.blog_writer.openai.OpenAI")
def test_generate_blog_handles_no_visuals(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"title": "Test Blog", "content_markdown": "# Test\\n\\nContent.", "image_suggestions": []}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = generate_blog(
        transcript="Simple transcript.",
        summary="A simple video.",
        chapters=[],
        visual_analysis=[],
        style="article"
    )

    assert result["title"] == "Test Blog"
    assert result["image_suggestions"] == []
