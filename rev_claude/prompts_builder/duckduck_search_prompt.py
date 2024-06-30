from typing import Tuple, List

from pydantic import BaseModel

from rev_claude.duckduck_search.utils import search_with_duckduckgo
from loguru import logger


class DuckDuckSearchPrompt(BaseModel):
    prompt: str
    max_results: int = 5
    base_prompt: str = """You can answer to the user's question based on the search results from the internet and provide the citation(xxx is a xxx [1])  if necessary 
, but you don't have to provide the reference at end of the answer.:
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
                # [[2]: https://news.cctv.com/china/](https://news.cctv.com/china/)
                hypper_link = f"[[{idx+1}]: {href}]({href})"
                hypper_link = f"\n{hypper_link}\n"
                if idx == 0:
                    hypper_link = "\n" + hypper_link
                hrefs.append(hypper_link)

            # TODO: this will be fixed later, just a trade off
            return (
                self.base_prompt.format(search_results=search_res, prompt=self.prompt),
                hrefs,
            )
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
