import os
import reflex as rx
from openai import OpenAI


import requests

CONVERSATION_ID = None


def stream_response(url, payload, headers):
    # 发起一个流式的 POST 请求
    global CONVERSATION_ID
    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        # 逐个字符处理响应体
        if not CONVERSATION_ID:
            CONVERSATION_ID = response.headers.get("conversation_id")
        for chunk in response.iter_content(decode_unicode=True, chunk_size=1):  # 设置chunk_size为1来逐个字符获取
            if chunk:  # 过滤掉keep-alive新行
                yield chunk  # 打印每个字符，end='' 防止自动换行


def build_url_headers_payload(message: str, model: str):
    # 你的API URL
    url = 'http://198.23.176.34:6238/api/v1/claude/chat'

    # 你的请求头
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # 你的请求体
    data = {
        "message": message,
        "model": model,
        "stream": True
    }
    if CONVERSATION_ID:
        data["conversation_id"] = CONVERSATION_ID

    # headers: {'date': 'Fri, 19 Apr 2024 16:25:12 GMT', 'server': 'uvicorn',
    #           'conversation_id': '411a9cff-fa7d-49be-9043-9471a29ad7fd',
    #           'content-type': 'text/event-stream; charset=utf-8', 'connection': 'close', 'transfer-encoding': 'chunked'}
    return url, headers, data






#

# Checking if the API key is set properly

class QA(rx.Base):
    """A question and answer pair."""

    question: str
    answer: str


DEFAULT_CHATS = {
    "Intros": [],
}


class State(rx.State):
    """The app state."""

    # A dict from the chat name to the list of questions and answers.
    chats: dict[str, list[QA]] = DEFAULT_CHATS

    # The current chat name.
    current_chat = "Intros"

    # The current question.
    question: str

    # Whether we are processing the question.
    processing: bool = False

    # The name of the new chat.
    new_chat_name: str = ""

    def create_chat(self):
        """Create a new chat."""
        # Add the new chat to the list of chats.
        self.current_chat = self.new_chat_name
        self.chats[self.new_chat_name] = []

    def delete_chat(self):
        """Delete the current chat."""
        del self.chats[self.current_chat]
        if len(self.chats) == 0:
            self.chats = DEFAULT_CHATS
        self.current_chat = list(self.chats.keys())[0]

    def set_chat(self, chat_name: str):
        """Set the name of the current chat.

        Args:
            chat_name: The name of the chat.
        """
        self.current_chat = chat_name

    @rx.var
    def chat_titles(self) -> list[str]:
        """Get the list of chat titles.

        Returns:
            The list of chat names.
        """
        return list(self.chats.keys())

    async def process_question(self, form_data: dict[str, str]):
        # Get the question from the form
        question = form_data["question"]

        # Check if the question is empty
        if question == "":
            return

        model = self.openai_process_question

        async for value in model(question):
            yield value

    async def openai_process_question(self, question: str):
        """Get the response from the API.

        Args:
            form_data: A dict with the current question.
        """

        # Add the question to the list of questions.
        qa = QA(question=question, answer="")
        self.chats[self.current_chat].append(qa)

        # Clear the input and start the processing.
        self.processing = True
        yield

        # Build the messages.
        messages = [
            {
                "role": "system",
                "content": "You are a friendly chatbot named Reflex. Respond in markdown.",
            }
        ]
        for qa in self.chats[self.current_chat]:
            messages.append({"role": "user", "content": qa.question})
            messages.append({"role": "assistant", "content": qa.answer})

        # Remove the last mock answer.
        messages = messages[:-1]

        # Start a new session to answer the question.
        session = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=messages,
            stream=True,
        )

        # Stream the results, yielding after every word.
        for item in session:
            if hasattr(item.choices[0].delta, "content"):
                answer_text = item.choices[0].delta.content
                # Ensure answer_text is not None before concatenation
                if answer_text is not None:
                    self.chats[self.current_chat][-1].answer += answer_text
                else:
                    # Handle the case where answer_text is None, perhaps log it or assign a default value
                    # For example, assigning an empty string if answer_text is None
                    answer_text = ""
                    self.chats[self.current_chat][-1].answer += answer_text
                self.chats = self.chats
                yield

        # Toggle the processing flag.
        self.processing = False
