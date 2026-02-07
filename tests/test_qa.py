# tests/test_qa.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.qa import answer_question


@patch("app.services.qa.openai.OpenAI")
def test_answer_question_returns_answer(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"answer": "He ran docker pull nginx at 5:02.", "relevant_timestamps": ["5:02"], "relevant_frames": []}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = answer_question(
        question="What command was run?",
        transcript="At 5:02 he ran docker pull nginx",
        visual_analysis=[],
        chapters=[]
    )

    assert "docker pull nginx" in result["answer"]
    assert "5:02" in result["relevant_timestamps"]


@patch("app.services.qa.openai.OpenAI")
def test_answer_question_includes_visual_context(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"answer": "A Docker architecture diagram is shown.", "relevant_timestamps": ["1:15"], "relevant_frames": ["/frames/frame_015.jpg"]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = answer_question(
        question="What diagram is shown?",
        transcript="Let me show you the architecture",
        visual_analysis=[{"timestamp": 75.0, "description": "Docker architecture diagram"}],
        chapters=[]
    )

    assert "diagram" in result["answer"]
