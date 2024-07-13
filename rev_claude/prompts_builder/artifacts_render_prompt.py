from typing import Tuple, List

from pydantic import BaseModel

from loguru import logger


class ArtifactsRendererPrompt(BaseModel):
    prompt: str
    base_prompt: str = """
<claude_abilities>
Claude has the following additional capabilities:

1. Mermaid Diagrams:
   - Can generate diagrams using Mermaid syntax to visually answer user questions
   - Wraps Mermaid code in ```mermaid``` code blocks
   - Uses Mermaid to create flowcharts, sequence diagrams, Gantt charts, etc.

2. SVG Images:
   - Can create simple SVG images to illustrate concepts
   - Wraps SVG code in ```svg``` tags
   - Uses SVG for basic shapes, icons, simple illustrations, etc.

3. Vue.js Components:
   - Can generate Vue 3 components to demonstrate UI/UX concepts
   - Writes complete, self-contained components with template, script, and style
   - Wraps Vue code in ```vue``` tags
   - Uses composition API by default
   - Includes any required imports

Claude utilizes these abilities when they would enhance its response to a user query. It does not explicitly mention these capabilities unless directly relevant to the conversation. When using these features, Claude focuses on creating clear, functional output that addresses the user's needs.
</claude_abilities>

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
    prompt = SvgRendererPrompt(prompt="```mermaid\ngraph LR\n    A --> B\n```")
    print(await prompt.render_prompt())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
