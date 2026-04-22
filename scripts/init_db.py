import asyncio

from memory.pipeline_history_store import PipelineHistoryStore
from memory.post_mortem_records import PostMortemStore
from memory.user_preference_profile import UserPreferenceStore


async def init():
    await PipelineHistoryStore().init_db()
    await UserPreferenceStore().init_db()
    await PostMortemStore().init_db()
    print("All tables created")

asyncio.run(init())
