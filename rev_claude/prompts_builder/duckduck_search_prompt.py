from typing import Tuple, List

from pydantic import BaseModel

from rev_claude.duckduck_search.utils import search_with_duckduckgo
from loguru import logger

class DuckDuckSearchPrompt(BaseModel):
    prompt: str
    max_results: int = 5
    base_prompt: str = \
"""You can answer to the user's question based on the search results from the internet and provide the link in markdown format if necessary like
citation ([xxx is a xxx][1] ) in paper:
{search_results}

Note: if the search results are not helpful, you can ignore this message and provide the answer directly.

User's question: 
{prompt}
    """



    async def render_prompt(self) -> Tuple[str, List]:
        try:
            _res = await search_with_duckduckgo(self.prompt, self.max_results)
            search_res = ""
            hrefs = []
            for idx, res in enumerate(_res):
                body = res["body"]
                href = res["href"]
                message = f"[{idx+1}]: {body}"
                search_res += message + "\n"
                hrefs.append("\n" * (1 + idx == 0) + f"[{idx+1}]: {href}" + "\n")

            # TODO: this will be fixed later, just a trade off
            return self.base_prompt.format(search_results=search_res, prompt=self.prompt), hrefs
        except Exception as e:
            from traceback import format_exc
            logger.error(format_exc())
            return self.prompt, []


async def main():
    prompt = DuckDuckSearchPrompt(prompt="姜萍的事件是什么？")
    print(await prompt.render_prompt())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())