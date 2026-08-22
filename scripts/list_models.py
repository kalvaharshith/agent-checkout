"""List all models available on your Groq account."""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
)

models = client.models.list()
print("AVAILABLE MODELS ON YOUR GROQ ACCOUNT:")
print("=" * 50)
for m in models.data:
    print(f"  {m.id}")