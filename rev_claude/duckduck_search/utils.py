import asyncio

from duckduckgo_search import AsyncDDGS


async def search_with_duckduckgo(query: str, max_results: int = 10):
    results = await AsyncDDGS().atext(query, max_results=max_results)
    return results



async def main():
    query = "今天天气北京怎么样"
    results = await search_with_duckduckgo(query)
    for result in results:
        print(result)

if __name__ == "__main__":
    asyncio.run(main())