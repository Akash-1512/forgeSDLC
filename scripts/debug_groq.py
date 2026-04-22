import asyncio

from langchain_core.messages import HumanMessage, SystemMessage

from model_router.adapters.groq_adapter import GroqAdapter


async def test():
    adapter = GroqAdapter(model="groq/llama-3.3-70b-versatile")
    response = await adapter.ainvoke([
        SystemMessage(content="You are a requirements analyst."),
        HumanMessage(content="Write a one-sentence PRD for a todo app.")
    ])
    print("Response:", response.content[:200])
    print("PASS")

asyncio.run(test())
