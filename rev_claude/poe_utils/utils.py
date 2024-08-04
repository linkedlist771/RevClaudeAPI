from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import uvicorn
from typing import AsyncGenerator
import json

from fastapi_poe.types import ProtocolMessage
from fastapi_poe.client import get_bot_response

from rev_claude.configs import POE_BOT_BASE_URL, POE_BOT_TEMPERATURE
from rev_claude.utils.key_config_utils import get_poe_bot_api_key

POE_BOT_API_KEY = get_poe_bot_api_key()


async def poe_bot_streaming_message(
    formatted_messages: list, bot_name: str
) -> AsyncGenerator[str, None]:
    """An async generator to stream responses from the POE API."""

    formatted_messages = [
        ProtocolMessage(
            role=msg["role"].lower().replace("assistant", "bot"),
            content=msg["content"],
            temperature=POE_BOT_TEMPERATURE,
        )
        for msg in formatted_messages
    ]

    # Create a base response template
    response_template = {
        "id": "chatcmpl-123",
        "object": "chat.completion.chunk",
        "created": 1694268190,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": "",  # Placeholder, to be filled for each partial response
                    "logprobs": None,
                    "finish_reason": None,
                },
            }
        ],
    }

    async for partial in get_bot_response(
        messages=formatted_messages,
        bot_name=bot_name,
        api_key=POE_BOT_API_KEY,
        base_url=POE_BOT_BASE_URL,
        skip_system_prompt=False,
        logit_bias={"24383": -100},
    ):
        # Fill the required field for this partial response
        response_template["choices"][0]["delta"]["content"] = partial.text

        # Create the SSE formatted string, and then yield
        # yield f"data: {json.dumps(response_template)}\n\n"
        yield partial.text
    # Send termination sequence
    # response_template["choices"][0]["delta"] = {}  # Empty 'delta' field
    # response_template["choices"][0][
    #     "finish_reason"
    # ] = "stop"  # Set 'finish_reason' to 'stop'

    # yield f"data: {json.dumps(response_template)}\n\ndata: [DONE]\n\n"
