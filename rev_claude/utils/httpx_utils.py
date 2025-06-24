from __future__ import annotations

import typing

import httpx
from httpx._config import DEFAULT_TIMEOUT_CONFIG
from httpx._types import (
    AuthTypes,
    CertTypes,
    CookieTypes,
    HeaderTypes,
    ProxiesTypes,
    ProxyTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
    TimeoutTypes,
    VerifyTypes,
)


async def async_stream(
    method: str,
    url: httpx.URL,
    *,
    params: QueryParamTypes | None = None,
    content: RequestContent | None = None,
    data: RequestData | None = None,
    files: RequestFiles | None = None,
    json: typing.Any | None = None,
    headers: HeaderTypes | None = None,
    cookies: CookieTypes | None = None,
    auth: AuthTypes | None = None,
    proxy: ProxyTypes | None = None,
    proxies: ProxiesTypes | None = None,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    follow_redirects: bool = False,
    verify: VerifyTypes = True,
    cert: CertTypes | None = None,
    trust_env: bool = True,
) -> typing.AsyncIterator[httpx.Response]:
    async with httpx.AsyncClient(
        cookies=cookies,
        proxy=proxy,
        proxies=proxies,
        cert=cert,
        verify=verify,
        timeout=timeout,
        trust_env=trust_env,
    ) as client:
        async with client.stream(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            headers=headers,
            json=json,
            params=params,
            auth=auth,
            follow_redirects=follow_redirects,
        ) as response:
            async for chunk in response.aiter_lines():
                yield chunk
