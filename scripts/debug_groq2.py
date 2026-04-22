import asyncio
import os

import httpx


async def test():
    key = os.getenv("GROQ_API_KEY", "")
    print("Key starts with:", key[:8], "...")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "say hi"}],
                "max_tokens": 10,
            },
        )
        print("Status:", r.status_code)
        print("Body:", r.text[:500])


asyncio.run(test())
