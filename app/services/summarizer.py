import json
import openai
from app.config import OPENAI_API_KEY

def summarize_transcript(transcript: str) -> dict:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze video transcripts. Return a JSON object with exactly these keys:\n"
                    '- "short": A 1-2 sentence summary\n'
                    '- "detailed": A 3-5 sentence detailed summary\n'
                    '- "chapters": An array of objects with "start", "end", "title" '
                    "representing logical sections of the video.\n"
                    "Estimate timestamps based on the transcript flow. "
                    "Return ONLY valid JSON, no markdown."
                )
            },
            {
                "role": "user",
                "content": f"Summarize this video transcript:\n\n{transcript[:8000]}"
            }
        ],
        temperature=0.3,
        max_tokens=1500
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "short": data.get("short", ""),
        "detailed": data.get("detailed", ""),
        "chapters": data.get("chapters", [])
    }
