import os
import asyncio
from app.config.settings import settings
from groq import Groq

client = Groq(api_key=settings.GROQ_API_KEY)

async def test_stt():
    with open("app/main.py", "rb") as dummy:
        print("Testing...")
        # Obviously this will fail because main.py is not an audio file, 
        # but we can see if the method signature is correct.
        try:
            transcription = client.audio.transcriptions.create(
                file=("test.webm", b"dummy audio data"),
                model="whisper-large-v3-turbo"
            )
            print("Response:", transcription)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_stt())
