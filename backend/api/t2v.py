import os
from pathlib import Path
from openai import OpenAI

# Load .env from backend root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)


def synthesize_text(text):
    response = client.audio.speech.create(
        model="openai/tts-1",
        voice="nova",
        input=text,
    )
    return response.content
