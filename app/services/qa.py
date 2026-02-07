# app/services/qa.py
import json
import openai
from app.config import OPENAI_API_KEY


def answer_question(question: str, transcript: str, visual_analysis: list, chapters: list) -> dict:
    """Answer a question about a processed video using transcript and visual context."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Build context from visual analysis
    visual_context = ""
    if visual_analysis:
        visual_lines = []
        for frame in visual_analysis:
            ts = frame.get("timestamp", 0)
            desc = frame.get("description", "")
            visual_lines.append(f"[{_seconds_to_timestamp(ts)}] {desc}")
        visual_context = "\n\nVisual observations:\n" + "\n".join(visual_lines)

    chapter_context = ""
    if chapters:
        chapter_lines = [f"- {ch.get('start', '')} to {ch.get('end', '')}: {ch.get('title', '')}" for ch in chapters]
        chapter_context = "\n\nChapters:\n" + "\n".join(chapter_lines)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer questions about videos based on their transcript and visual analysis. "
                    "Return a JSON object with:\n"
                    '- "answer": Your answer to the question (2-3 sentences)\n'
                    '- "relevant_timestamps": Array of relevant timestamp strings (e.g., ["5:02", "5:15"])\n'
                    '- "relevant_frames": Array of frame paths if visual frames are relevant, else empty array\n'
                    "Return ONLY valid JSON, no markdown."
                )
            },
            {
                "role": "user",
                "content": f"Transcript:\n{transcript[:6000]}{visual_context}{chapter_context}\n\nQuestion: {question}"
            }
        ],
        temperature=0.3,
        max_tokens=500
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "answer": data.get("answer", ""),
        "relevant_timestamps": data.get("relevant_timestamps", []),
        "relevant_frames": data.get("relevant_frames", [])
    }


def _seconds_to_timestamp(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
