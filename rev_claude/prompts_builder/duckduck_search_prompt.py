

from pydantic import BaseModel

from rev_claude.duckduck_search.utils import search_with_duckduckgo
from loguru import logger

class DuckDuckSearchPrompt(BaseModel):
    prompt: str
    max_results: int = 5
    base_prompt: str = \
"""You can answer to the user's question based on the search results from the internet and provide the link in markdown format if necessary like
citation in paper:
{search_results}

User's question: 
{prompt}
    """

    async def render_prompt(self) -> str:
        try:
            res = await search_with_duckduckgo(self.prompt, self.max_results)
            search_res = ""
            for res in res:
                body = res["body"]
                href = res["href"]
                message = f"{href}: {body}"
                search_res += message + "\n"

            return self.base_prompt.format(search_results=search_res, prompt=self.prompt)
        except Exception as e:
            from traceback import format_exc
            logger.error(format_exc())
            return self.prompt


async def main():
    prompt = DuckDuckSearchPrompt(prompt="姜萍的事件是什么？")
    print(await prompt.render_prompt())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())