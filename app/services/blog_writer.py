# app/services/blog_writer.py
import json
import openai
from app.config import OPENAI_API_KEY


def generate_blog(
    transcript: str,
    summary: str,
    chapters: list,
    visual_analysis: list,
    style: str = "article"
) -> dict:
    """Convert video content into a blog article."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    chapter_text = ""
    if chapters:
        chapter_lines = [f"- {ch.get('start', '')} to {ch.get('end', '')}: {ch.get('title', '')}" for ch in chapters]
        chapter_text = "\n\nChapters:\n" + "\n".join(chapter_lines)

    visual_text = ""
    if visual_analysis:
        visual_lines = [f"- [{v.get('timestamp', 0)}s] {v.get('description', '')}" for v in visual_analysis]
        visual_text = "\n\nVisual scenes:\n" + "\n".join(visual_lines)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You convert video transcripts into well-structured blog articles in '{style}' style. "
                    "Return a JSON object with:\n"
                    '- "title": A compelling blog title\n'
                    '- "content_markdown": The full article in markdown format, using the transcript content '
                    "to write a comprehensive article with headers, paragraphs, code blocks if relevant, and lists.\n"
                    '- "image_suggestions": Array of objects with "timestamp" (float), "caption" (string), '
                    'and "insert_after" (markdown heading where the image fits best). '
                    "Only suggest images where visual frames were available.\n"
                    "Return ONLY valid JSON, no markdown wrapping."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Summary: {summary}\n\n"
                    f"Transcript:\n{transcript[:8000]}"
                    f"{chapter_text}{visual_text}"
                )
            }
        ],
        temperature=0.4,
        max_tokens=3000
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "title": data.get("title", ""),
        "content_markdown": data.get("content_markdown", ""),
        "image_suggestions": data.get("image_suggestions", [])
    }
