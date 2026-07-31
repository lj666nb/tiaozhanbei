import asyncio, sys, importlib
sys.path.insert(0, '/app')
import services.ai_service
importlib.reload(services.ai_service)
from services.ai_service import web_search

async def test():
    results = await web_search('AI Agent 2026', max_results=3)
    print('Results:', len(results))
    for r in results:
        title = r.get('title', '')
        print(' -', title[:80])

asyncio.run(test())
