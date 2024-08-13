#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import re
import httpx
import asyncio
from httpx_sse._decoders import SSEDecoder
from loguru import logger
from fake_useragent import UserAgent
from fastapi import UploadFile, status, HTTPException
from fastapi.responses import JSONResponse
import itertools
import uuid
import random
import os


from rev_claude.utils.file_utils import DocumentConverter
from rev_claude.REMINDING_MESSAGE import (
    NO_EMPTY_PROMPT_MESSAGE,
    PROMPT_TOO_LONG_MESSAGE,
    EXCEED_LIMIT_MESSAGE,
    PLUS_EXPIRE,
)
from rev_claude.configs import (
    STREAM_CONNECTION_TIME_OUT,
    STREAM_TIMEOUT,
    PROXIES,
    USE_PROXY,
    CLAUDE_OFFICIAL_EXPIRE_TIME,
    CLAUDE_OFFICIAL_REVERSE_BASE_URL,
)
from rev_claude.status.clients_status_manager import ClientsStatusManager
from rev_claude.status_code.status_code_enum import (
    HTTP_481_IMAGE_UPLOAD_FAILED,
    HTTP_482_DOCUMENT_UPLOAD_FAILED,
)


def generate_trace_id():
    # 生成一个随机的 UUID
    trace_id = uuid.uuid4().hex

    # 生成一个随机的 Span ID，长度为16的十六进制数
    span_id = os.urandom(8).hex()

    # 设定采样标识，这里假设采样率为1/10，即10%的数据发送
    sampled = random.choices([0, 1], weights=[9, 1])[0]

    # 将三个部分组合成完整的 Sentry-Trace
    sentry_trace = f"{trace_id}-{span_id}-{sampled}"
    return sentry_trace


ua = UserAgent()
filtered_browsers = list(
    filter(
        lambda x: x["browser"] in ua.browsers
        and x["os"] in ua.os
        and x["percent"] >= ua.min_percentage,
        ua.data_browsers,
    )
)

# 使用itertools.cycle创建一个无限迭代器
infinite_iter = itertools.cycle(filtered_browsers)


def get_random_user_agent():
    return next(infinite_iter).get("useragent")


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

    async def retrieve_reverse_official_route(self, unique_name):
        payload = {
            "session_key": self.retrieve_session_key(),
            "unique_name": unique_name,
            "expires_in": CLAUDE_OFFICIAL_EXPIRE_TIME,
        }
        async with httpx.AsyncClient() as client:
            login_url = (
                CLAUDE_OFFICIAL_REVERSE_BASE_URL + "/manage-api/auth/oauth_token"
            )
            response = await client.post(login_url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return None

    async def __set_organization_id__(self):
        self.organization_id = await self.__async_get_organization_id()
        return self.organization_id

    def retrieve_session_key(self):
        cookie_list = self.cookie.split(";")
        for cookie_key_pair in cookie_list:
            if "sk-ant-si" in cookie_key_pair:
                return cookie_key_pair.strip().replace("sessionKey=", "")
        return

    def build_organization_headers(self):
        return {
            "User-Agent": get_random_user_agent(),
            # "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
        }

    async def __async_get_organization_id(self):
        url = "https://claude.ai/api/organizations"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.build_organization_headers())
            res_str = response.text
            logger.debug(f"res_str : {res_str}")
            res = response.json()
            if "We are unable to serve your request" in res_str:
                raise Exception("We are unable to serve your request")
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

    # Lists all the conversations you had with Claud

    # Send Message to Claude

    def build_stream_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/124.0",
            "Accept": "text/event-stream, text/event-stream",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://claude.ai/chats",
            "Content-Type": "application/json",
            "Origin": "https://claude.ai",
            "DNT": "1",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "TE": "trailers",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "Windows",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sentry-Trace": generate_trace_id()[2:],
        }

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
            "rendering_mode": "raw",
        }
        if client_type != "plus":
            __payload.pop("model")
        # payload = json.dumps(__payload)
        payload = __payload

        headers = self.build_stream_headers()
        max_retry = 5
        current_retry = 0
        response_text = ""
        client_manager = ClientsStatusManager()
        if len(prompt) <= 0:
            yield NO_EMPTY_PROMPT_MESSAGE
            return
        while current_retry < max_retry:
            try:
                works_fine = False
                async with httpx.AsyncClient(
                    timeout=STREAM_TIMEOUT, proxies=PROXIES if USE_PROXY else None
                ) as client:
                    # logger.debug(f"url:\n {url}")
                    # logger.debug(f"headers:\n {headers}")
                    decoder = SSEDecoder()

                    async with client.stream(
                        method="POST",
                        url=url,
                        headers=headers,
                        json=payload,
                        timeout=10,
                    ) as response:
                        async for text in response.aiter_lines():
                            # logger.debug(f"raw text: {text}")
                            # async with client.stream(method="POST", url=url, headers=headers, json=data) as response:
                            if works_fine == False:
                                logger.info(
                                    f"Streaming message works fine and get the first text:\n {text}"
                                )
                                works_fine = True
                            # logger.info(f"raw text: {text}")
                            # convert a byte string to a string
                            # logger.info(f"raw text: {text}")
                            # logger.debug(f"raw text: {text}")
                            if ("Invalid model" in text) or (
                                "Organization has no active Self-Serve Stripe" in text
                            ):
                                logger.error(f"Invalid model : {text}")
                                client_manager = ClientsStatusManager()
                                await client_manager.set_client_error(
                                    client_type, client_idx
                                )
                                logger.error(f"设置账号状态为error")
                                yield PLUS_EXPIRE
                                await asyncio.sleep(0)  # 模拟异步操作, 让出权限
                                break
                            elif "permission_error" in text:
                                logger.error(f"permission_error : {text}")
                                raise Exception(text)
                                # ClientsStatusManager

                            if "exceeded_limit" in text:
                                # 对于plus用户只opus model才设置
                                # if ClaudeModels.model_is_plus(model): 这个地方就不需要check了
                                # logger.debug(f"client_type: {client_type}")
                                client_type = client_type.replace("normal", "basic")
                                dict_res = json.loads(text)
                                error_message = dict_res["error"]
                                resetAt = int(
                                    json.loads(error_message["message"])["resetsAt"]
                                )
                                refresh_time = resetAt
                                start_time = int(refresh_time) - 8 * 3600
                                client_manager = ClientsStatusManager()
                                await client_manager.set_client_limited(
                                    client_type, client_idx, start_time, model
                                )

                                logger.error(f"exceeded_limit : {text}")
                                yield EXCEED_LIMIT_MESSAGE
                                await asyncio.sleep(0)  # 模拟异步操作, 让出权限
                                break

                            if "too long" in text:
                                yield PROMPT_TOO_LONG_MESSAGE
                                await asyncio.sleep(0)  # 模拟异步操作, 让出权限
                                break  # 忘了加break了

                            if "concurrent connections has" in text:
                                logger.error(
                                    f"concurrent connections has exceeded the limit"
                                )
                                raise Exception(
                                    "concurrent connections has exceeded the limit"
                                )
                            if "Rate exceeded" in text:
                                logger.error(f"Rate exceeded: {text}")
                                raise Exception("Rate exceeded")

                            if ("error" in text) and ("completion" not in text):
                                logger.error(f"error: {text}")
                                # 最后再捕获一下报错，如果好友就直接raise 一个error
                                raise Exception(text)

                            # response_parse_text = await self.parse_text(
                            #     text, client_type, client_idx, model
                            # )
                            line = text.rstrip("\n")
                            sse = decoder.decode(line)
                            response_parse_text = ""
                            if sse is not None:
                                data = json.loads(sse.data)
                                if "completion" in list(data.keys()):
                                    message = data["completion"]
                                    response_parse_text = message

                            # logger.info(f"parsed text: {response_parse_text}")
                            if response_parse_text:
                                await client_manager.set_client_status(
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

    def build_new_chat_headers(self, uuid):
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

    def build_get_conversation_histories_headers(self, url_path):
        return {
            "Alt-Svc": "h3=':443'; ma=86400",
            "Cf-Cache-Status": "DYNAMIC",
            # "Cf-Ray": "89a7300dae7c827c-TPE",
            "Content-Encoding": "br",
            # "Content-Security-Policy": "script-src 'strict-dynamic' 'wasm-unsafe-eval' https: 'nonce-17ba8129-a77d-4672-b23d-4662a4cbb39d'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; block-all-mixed-content; upgrade-insecure-requests",
            "Content-Type": "application/json",
            # "Date": "Thu, 27 Jun 2024 17:34:25 GMT",
            "Server": "cloudflare",
            "Set-Cookie": self.cookie,
            # f"activitySessionId=ad8f37d8-d54a-4730-be0a-c86e39b90f30; Path=/; Expires=Fri, 28 Jun 2024 05:34:25 GMT; Secure; HttpOnly; SameSite=lax",
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "Vary": "RSC, Next-Router-State-Tree, Next-Router-Prefetch, Next-Url",
            "Via": "1.1 google",
            "X-Activity-Session-Id": "ad8f37d8-d54a-4730-be0a-c86e39b90f30",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Request-Pathname": url_path,
            # "/api/organizations/dc00b293-7c1c-43f9-ac4a-d14d501e73ca/chat_conversations/0796759-9efe-4875-9984-8dc2021640bc",
            "X-Xss-Protection": "1; mode=block",
        }

    async def get_conversation_histories(self, conversation_id):
        # Q:与prefix相对的是什么
        # A: 与prefix相对的是suffix
        path = f"/api/organizations/{self.organization_id}/chat_conversations/{conversation_id}"
        # url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations/{conversation_id}"
        url = f"https://claude.ai{path}"
        headers = self.build_get_conversation_histories_headers(path)
        async with httpx.AsyncClient(
            # proxies=PROXIES if USE_PROXY else None,
            timeout=STREAM_CONNECTION_TIME_OUT,
        ) as client:
            response = await client.get(url, headers=headers)
        return response.json()

    async def create_new_chat(self, model):
        url = f"https://claude.ai/api/organizations/{self.organization_id}/chat_conversations"
        uuid = self.generate_uuid()
        # payload = json.dumps({"uuid": uuid, "name": "", "model": model})
        payload = {"uuid": uuid, "name": ""}

        headers = self.build_new_chat_headers(uuid)
        # logger.debug(f"headers: \n{headers}")
        # logger.debug(f"payload: \n{payload}")
        async with httpx.AsyncClient(
            # proxies=PROXIES if USE_PROXY else None,
            timeout=STREAM_CONNECTION_TIME_OUT,
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
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
