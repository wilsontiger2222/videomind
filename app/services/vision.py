# app/services/vision.py
import base64
import openai
from app.config import OPENAI_API_KEY


def analyze_frame(frame_path: str) -> str:
    """Send a single frame to GPT-4o Vision and get a description."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You describe video frames concisely. Focus on what is visually "
                    "shown: text on screen, UI elements, diagrams, code, people, "
                    "actions. One sentence, max 50 words."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Describe what is shown in this video frame."
                    }
                ]
            }
        ],
        max_tokens=100,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()


def analyze_frames(frames: list) -> list:
    """Analyze a list of frames with GPT-4o Vision."""
    results = []
    for frame in frames:
        try:
            description = analyze_frame(frame["path"])
        except Exception:
            description = "Analysis failed"

        results.append({
            "timestamp": frame["timestamp"],
            "frame_path": frame["path"],
            "description": description
        })

    return results
