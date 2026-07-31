import asyncio, sys
sys.path.insert(0, '/app')
from services.ai_service import web_search
async def test():
    results = await web_search('AI Agent', max_results=3)
    print(f'Results: {len(results)}')
    for r in results:
        print(f'  - {r["title"][:80]}')
asyncio.run(test())
