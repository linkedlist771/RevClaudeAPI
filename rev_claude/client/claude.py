#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json, os, uuid
import re

from curl_cffi import requests
import httpx
import asyncio
from loguru import logger
from fastapi import HTTPException

from rev_claude.REMINDING_MESSAGE import (
    NO_EMPTY_PROMPT_MESSAGE,
    PROMPT_TOO_LONG_MESSAGE,
    EXCEED_LIMIT_MESSAGE,
)
from rev_claude.configs import STREAM_CONNECTION_TIME_OUT, STREAM_TIMEOUT
from rev_claude.status.clients_status_manager import ClientsStatusManager
from fastapi import UploadFile, status, HTTPException
from fastapi.responses import JSONResponse
from rev_claude.status_code.status_code_enum import (
    HTTP_481_IMAGE_UPLOAD_FAILED,
    HTTP_482_DOCUMENT_UPLOAD_FAILED,
)
from rev_claude.utils.file_utils import DocumentConverter
from rev_claude.utils.httpx_utils import async_stream
from rev_claude.utils.sse_utils import build_sse_data


from fake_useragent import UserAgent

ua = UserAgent()


def get_random_user_agent():
    # 获取 iPhone 的用户代理
    return ua.random
async def upload_attachment_for_fastapi(file: UploadFile):
    # 从 UploadFile 对象读取文件内容
    # 直接try to read
    try:
        document_converter = DocumentConverter(upload_file=file)
        result = await document_converter.convert()

        if result is None:
            logger.error(f"Unsupported file type: {file.filename}")
            # return JSONResponse(
            #     content={"message": "无法处理该文件类型"}, status_code=HTTP_482_DOCUMENT_UPLOAD_FAILED
            # )
            raise HTTPException(
                status_code=HTTP_482_DOCUMENT_UPLOAD_FAILED,
                detail="无法处理该文件类型",
            )

        return JSONResponse(content=result.model_dump())

    except Exception as e:
        logger.error(f"Meet Error when converting file to text: \n{e}")
        # return JSONResponse(content={"message": "处理上传文件报错"}, status_code=HTTP_482_DOCUMENT_UPLOAD_FAILED)
        raise HTTPException(
            status_code=HTTP_482_DOCUMENT_UPLOAD_FAILED,
            detail="处理上传文件报错",
        )


class Client:
    def fix_sessionKey(self, cookie):
        if "sessionKey=" not in cookie:
            cookie = "sessionKey=" + cookie
        return cookie

    def __init__(self, cookie, cookie_key=None):
        self.cookie = self.fix_sessionKey(cookie)
        self.cookie_key = cookie_key
        # self.organization_id = self.get_organization_id()

    async def __set_organization_id__(self):
        self.organization_id = await self.__async_get_organization_id()

    def build_organization_headers(self):
        return {
            "User-Agent": get_random_user_agent(),
                #"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
        }

    def get_organization_id(self):
        url = "https://claude.ai/api/organizations"
        headers = self.build_organization_headers()
        response = requests.get(url, headers=headers, impersonate="chrome110")
        res = json.loads(response.text)
        uuid = res[0]["uuid"]
        return uuid

    async def __async_get_organization_id(self):
        url = "https://claude.ai/api/organizations"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.build_organization_headers())
            res = response.json()
            logger.debug(f"res : {res}")
            uuid = res[0]["uuid"]
            return uuid

    def get_content_type(self, file_path):
        # Function to determine content type based on file extension
        extension = os.path.splitext(file_path)[-1].lower()
        if extension == ".pdf":
            return "application/pdf"
        elif extension == ".txt":
            return "text/plain"
        elif extension == ".csv":
            return "text/csv"
        # Add more content types as needed for other file types
        else:
            return "application/octet-stream"

    # Lists all the conversations you had with Claude
    def list_all_conversations(self):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
        }

        response = requests.get(url, headers=headers, impersonate="chrome110")
        conversations = response.json()

        # Returns all conversation information in a list
        if response.status_code == 200:
            return conversations
        else:
            print(f"Error: {response.status_code} - {response.text}")

    # Send Message to Claude


    def build_stream_headers(self):
        return {
            "User-Agent": get_random_user_agent(),
            # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept": "text/event-stream, text/event-stream",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Origin": "https://claude.ai",
            "DNT": "1",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }

    async def parse_text(self, text, client_type, client_idx):
        # TODO: add error handling for invalid model.
        try:
            parsed_response = json.loads(text)
            if "error" in parsed_response:

                # print("Error Message:", error_message)
                logger.error(f"Error Message: {parsed_response}")
                # raise Exception(error_message)
                # ClientsStatusManager
                if "exceeded_limit" in text:
                    dict_res = json.loads(text)
                    error_message = dict_res["error"]
                    resetAt = int(json.loads(error_message["message"])["resetsAt"])
                    refresh_time = resetAt
                    start_time = int(refresh_time) - 8 * 3600
                    client_manager = ClientsStatusManager()
                    client_manager.set_client_limited(
                        client_type, client_idx, start_time
                    )
                elif "permission" in text:
                    logger.error(f"permission_error : {text}")

                    client_manager = ClientsStatusManager()
                    client_manager.set_client_error(client_type, client_idx)
                    logger.error(f"设置账号状态为error")

        except json.JSONDecodeError:
            events = []
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    parts = line.split(": ")
                    if len(parts) == 2:
                        event_type, data = parts
                        if data != "completion" and data != "ping":
                            try:
                                event_data = json.loads(data)
                                events.append(event_data["completion"])
                            except json.JSONDecodeError:
                                # logger.error(f"CLAUDE STREAM ERROR: {data}")
                                if not data.endswith('"'):
                                    data = data + '"'
                                pattern = r'"completion":"(.*?)(?<!\\)"'
                                match = re.search(pattern, data)
                                if match:
                                    completion_content = match.group(
                                        1
                                    )  # 提取第一个捕获组的内容
                                    events.append(completion_content)
                            except Exception as e:
                                logger.error(f"Error: {e}")
            return events

    # Send and Response Stream Message to Claude

    async def stream_message(
        self,
        prompt,
        conversation_id,
        model,
        client_type,
        client_idx,
        attachments=None,
        files=None,
        call_back=None,
        timeout=120,
    ):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations/{conversation_id}/completion"
        __payload = {
            "attachments": attachments,  # attachments is a list
            "files": [] if files is None else files,
            "model": model,  # TODO: 当账号类型为普通账号的时候，这里不需要传入model
            "timezone": "Europe/London",
            "prompt": f"{prompt}",
        }
        if client_type != "plus":
            __payload.pop("model")
        # payload = json.dumps(__payload)
        payload = __payload

        headers = self.build_stream_headers()
        max_retry = 3
        current_retry = 0
        response_text = ""
        client_manager = ClientsStatusManager()
        if len(prompt) <= 0:
            yield NO_EMPTY_PROMPT_MESSAGE
            return
            # 这里要return吗
        logger.debug(f"url:\n {url}")
        logger.debug(f"headers:\n {headers}")
        logger.debug(f"payload:\n {payload}")
        while current_retry < max_retry:
            try:
                # async for text in async_stream(
                #     "POST",
                #     httpx.URL(url),
                #     headers=headers,
                #     json=payload,
                #     timeout=STREAM_TIMEOUT,
                # ):

                async with httpx.AsyncClient(timeout=STREAM_CONNECTION_TIME_OUT) as client:
                 async with client.stream(method="POST", url=url, headers=headers, json=payload) as response:
                  async for text in response.aiter_lines():
                    # logger.debug(f"raw text: {text}")
                    # async with client.stream(method="POST", url=url, headers=headers, json=data) as response:

                    # logger.info(f"raw text: {text}")
                    # convert a byte string to a string
                    # logger.info(f"raw text: {text}")
                    if "permission_error" in text:
                        logger.error(f"permission_error : {text}")
                        raise Exception(text)
                        # ClientsStatusManager
                    if "exceeded_limit" in text:
                        # 对于plus用户只opus model才设置
                        if client_type == "plus":
                            if "opus" in model:
                                dict_res = json.loads(text)
                                error_message = dict_res["error"]
                                resetAt = int(
                                    json.loads(error_message["message"])["resetsAt"]
                                )
                                refresh_time = resetAt
                                start_time = int(refresh_time) - 8 * 3600
                                client_manager = ClientsStatusManager()
                                client_manager.set_client_limited(
                                    client_type, client_idx, start_time
                                )
                        else:
                            dict_res = json.loads(text)
                            error_message = dict_res["error"]
                            resetAt = int(
                                json.loads(error_message["message"])["resetsAt"]
                            )
                            refresh_time = resetAt
                            start_time = int(refresh_time) - 8 * 3600
                            client_manager = ClientsStatusManager()
                            client_manager.set_client_limited(
                                client_type, client_idx, start_time
                            )
                        logger.error(f"exceeded_limit : {text}")
                        yield EXCEED_LIMIT_MESSAGE
                        await asyncio.sleep(0)  # 模拟异步操作, 让出权限
                        break

                    elif "prompt is too long" in text:
                        yield PROMPT_TOO_LONG_MESSAGE
                        await asyncio.sleep(0)  # 模拟异步操作, 让出权限

                    elif "concurrent connections has" in text:
                        logger.error(f"concurrent connections has exceeded the limit")
                        raise Exception("concurrent connections has exceeded the limit")

                    response_parse_text = await self.parse_text(
                        text, client_type, client_idx
                    )
                    # logger.info(f"parsed text: {response_parse_text}")
                    if response_parse_text:
                        client_manager.set_client_status(
                            client_type, client_idx, "active"
                        )
                        resp_text = "".join(response_parse_text)
                        response_text += resp_text
                        yield resp_text
                        await asyncio.sleep(0)  # 模拟异步操作, 让出权限
                logger.info(f"Response text:\n {response_text}")
                if call_back:
                    await call_back(response_text)
                break
            except Exception as e:
                import traceback

                current_retry += 1
                logger.error(
                    f"Failed to stream message. Retry {current_retry}/{max_retry}. Error: {traceback.format_exc()}"
                )
                if current_retry == max_retry:
                    logger.error(f"Failed to stream message after {max_retry} retries.")
                    yield "error: " + str(e)
                else:
                    logger.info("Retrying in 3 second...")
                    await asyncio.sleep(3)

    # Deletes the conversation
    def delete_conversation(self, conversation_id):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations/{conversation_id}"
        payload = json.dumps(f"{conversation_id}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Content-Length": "38",
            "Referer": "https://claude.ai/chats",
            "Origin": "https://claude.ai",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "TE": "trailers",
        }

        response = requests.delete(
            url, headers=headers, data=payload, impersonate="chrome110"
        )

        # Returns True if deleted or False if any error in deleting
        if response.status_code == 204:
            return True
        else:
            return False

    # Returns all the messages in conversation
    def chat_conversation_history(self, conversation_id):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations/{conversation_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
        }

        response = requests.get(url, headers=headers, impersonate="chrome110")

        # List all the conversations in JSON
        return response.json()

    def generate_uuid(self):
        random_uuid = uuid.uuid4()
        random_uuid_str = str(random_uuid)
        formatted_uuid = f"{random_uuid_str[0:8]}-{random_uuid_str[9:13]}-{random_uuid_str[14:18]}-{random_uuid_str[19:23]}-{random_uuid_str[24:]}"
        return formatted_uuid

    def build_new_chat_payload(self, uuid):
        return {
            # "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "User-Agent": get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": f"https://claude.ai/chat/{uuid}",
            "Content-Type": "application/json",
            "Origin": "https://claude.ai",
            "DNT": "1",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }

    async def create_new_chat(self, model):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations"
        uuid = self.generate_uuid()
        # payload = json.dumps({"uuid": uuid, "name": "", "model": model})
        payload = {"uuid": uuid, "name": ""}

        headers = self.build_new_chat_payload(uuid)
        logger.debug(f"headers: \n{headers}")
        logger.debug(f"payload: \n{payload}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
        return response.json()

    async def set_conversation_model(self, model, uuid):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations"
        uuid = self.generate_uuid()
        # payload = json.dumps({"uuid": uuid, "name": "", "model": model})
        payload = json.dumps({"uuid": uuid, "name": ""})

        headers = self.build_new_chat_payload(uuid)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=payload)
        return response.json()


    # Resets all the conversations
    def reset_all(self):
        conversations = self.list_all_conversations()

        for conversation in conversations:
            conversation_id = conversation["uuid"]
            delete_id = self.delete_conversation(conversation_id)

        return True

    def upload_attachment(self, file_path):
        if file_path.endswith(".txt"):
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_type = "text/plain"
            with open(file_path, "r", encoding="utf-8") as file:
                file_content = file.read()

            return {
                "file_name": file_name,
                "file_type": file_type,
                "file_size": file_size,
                "extracted_content": file_content,
            }
        url = "https://claude.ai/api/convert_document"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Origin": "https://claude.ai",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "TE": "trailers",
        }

        file_name = os.path.basename(file_path)
        content_type = self.get_content_type(file_path)

        files = {
            "file": (file_name, open(file_path, "rb"), content_type),
            "orgUuid": (None, self.organization_id),
        }

        response = requests.post(url, headers=headers, files=files)
        if response.status_code == 200:
            return response.json()
        else:
            return False

    async def upload_images(self, image_file: UploadFile):

        url = f"https://claude.ai/api/{self.organization_id}/upload"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Origin": "https://claude.ai",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "TE": "trailers",
        }
        time_out = 10
        try:
            async with httpx.AsyncClient(timeout=time_out) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    files={
                        "file": (
                            image_file.filename,
                            image_file.file,
                            image_file.content_type,
                        )
                    },
                )
                logger.info(f"response: \n{response.json()} ")
                if response.status_code == 200:
                    res_json = response.json()
                    return JSONResponse(content=res_json)

                else:
                    # return JSONResponse(
                    #     content={"message": "Failed to upload image"},
                    #     status_code=HTTP_481_IMAGE_UPLOAD_FAILED,
                    # )
                    raise HTTPException(
                        status_code=HTTP_481_IMAGE_UPLOAD_FAILED,
                        detail="Failed to upload image",
                    )

        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            raise HTTPException(
                status_code=HTTP_481_IMAGE_UPLOAD_FAILED,
                detail="Failed to upload image",
            )

    # Renames the chat conversation title
    def rename_chat(self, title, conversation_id):
        url = "https://claude.ai/api/rename_chat"

        payload = json.dumps(
            {
                "organization_uuid": f"{self.organization_id}",
                "conversation_uuid": f"{conversation_id}",
                "title": f"{title}",
            }
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Referer": "https://claude.ai/chats",
            "Origin": "https://claude.ai",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "TE": "trailers",
        }

        response = requests.post(
            url, headers=headers, data=payload, impersonate="chrome110"
        )

        if response.status_code == 200:
            return True
        else:
            return False
