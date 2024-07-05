from typing import Tuple, List

from pydantic import BaseModel

from loguru import logger


class SvgRendererPrompt(BaseModel):
    prompt: str
    base_prompt: str = """# Ability
    - You can use the ```mermaid``` syntax to draw a diagram to answer the user's question.
    - You can use the ```svg``` tag to render a svg image to answer the user's question.
{prompt}
    """

    async def render_prompt(self) -> str:
        try:
            return self.base_prompt.format(prompt=self.prompt)

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
