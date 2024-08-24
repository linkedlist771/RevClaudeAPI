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

3. Vue3 Components:
   
   - Can generate Vue 3 components to demonstrate UI/UX concepts
   - Writes only one complete, self-contained components with template, script, and style and don't use it in another component
   - Wraps the only one Vue code in ```vue``` tags
   - Uses composition API by default
   - Includes any required imports
   - **Important**: Claude can only generate web use vue3, not html nor React, raw html or React code is not allowed. 
   Here is an example for QQ login UI:
   ```vue
   <template>
  <div class="login-container">
    <div class="login-box">
      <div class="logo">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
          <circle cx="50" cy="50" r="45" fill="#12B7F5"/>
          <path d="M30,50 Q50,30 70,50 Q50,70 30,50" fill="white" stroke="white" stroke-width="5"/>
        </svg>
      </div>
      <form @submit.prevent="handleLogin">
        <input type="text" v-model="username" placeholder="QQ号码/手机/邮箱" />
        <input type="password" v-model="password" placeholder="密码" />
        <button type="submit">登 录</button>
      </form>
      <div class="options">
        <a href="#">忘记密码</a>
        <a href="#">注册新账号</a>
      </div>
      <div class="alternative-login">
        <span>其他方式登录：</span>
        <a href="#" class="icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <path fill="#999" d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4M12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6M12,8A4,4 0 0,0 8,12A4,4 0 0,0 12,16A4,4 0 0,0 16,12A4,4 0 0,0 12,8Z" />
          </svg>
        </a>
        <a href="#" class="icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
            <path fill="#999" d="M17,2V2H17V6H15C14.31,6 14,6.81 14,7.5V10H14L17,10V14H14V22H10V14H7V10H10V6A4,4 0 0,1 14,2H17Z" />
          </svg>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const username = ref('');
const password = ref('');

const handleLogin = () => {
  // 这里处理登录逻辑
  console.log('Login attempt:', username.value, password.value);
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #F1F1F1;
  font-family: Arial, sans-serif;
}

.login-box {
  background-color: white;
  padding: 30px;
  border-radius: 4px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  width: 300px;
}

.logo {
  text-align: center;
  margin-bottom: 20px;
}

form {
  display: flex;
  flex-direction: column;
}

input {
  margin-bottom: 10px;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  background-color: #12B7F5;
  color: white;
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover {
  background-color: #0EA2E4;
}

.options {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
}

.options a {
  color: #12B7F5;
  text-decoration: none;
  font-size: 14px;
}

.alternative-login {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: #999;
}

.icon {
  margin-left: 10px;
}
</style>
```

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
