
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing from your .env file.")

client = Groq(api_key=api_key)

try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: GROQ_CONNECTION_OK",
            }
        ],
        temperature=0,
        max_tokens=30,
    )

    print("Groq chat-completion test successful!")
    print("Model response:", response.choices[0].message.content)

except Exception as exc:
    print("Groq API request failed.")
    print("Error type:", type(exc).__name__)
    print("Error details:", str(exc))
