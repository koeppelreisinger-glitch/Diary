import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException

logger = logging.getLogger(__name__)


class TokenHubChatService:
    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.TOKENHUB_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        # doc14 §3.3/§3.4: 后台 AI 调用强制 JSON 输出时传入 response_format
        if response_format:
            payload["response_format"] = response_format
        return await self._post_chat_completion(payload)

    async def create_text_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        response_data = await self.create_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
            max_tokens=max_tokens,
        )
        return self.extract_text_content(response_data).strip()

    def extract_text_content(self, response_data: dict[str, Any]) -> str:
        choices = response_data.get("choices") or []
        if not choices:
            raise ErrorResponseAPIException(
                status_code=502,
                detail="AI 响应中缺少 choices",
                code=50206,
            )

        message = (choices[0] or {}).get("message") or {}
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "".join(text_parts)

        return str(content)

    async def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": self._build_authorization_header(),
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.TOKENHUB_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    settings.TOKENHUB_CHAT_COMPLETIONS_URL,
                    headers=headers,
                    json=payload,
                )
                if response.status_code != 200:
                    detail = response.text
                    logger.error(
                        "TokenHub request failed: status=%s body=%s",
                        response.status_code,
                        detail[:500],
                    )
                    raise ErrorResponseAPIException(
                        status_code=502,
                        detail=f"AI 请求失败，状态码 {response.status_code}",
                        code=50203,
                    )
                return response.json()

        except ErrorResponseAPIException:
            raise
        except httpx.TimeoutException as exc:
            logger.error("TokenHub request timed out: %s", exc)
            raise ErrorResponseAPIException(
                status_code=502,
                detail="AI 请求超时，请稍后重试",
                code=50207,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("TokenHub network error: %s", exc)
            raise ErrorResponseAPIException(
                status_code=502,
                detail=f"AI 网络请求失败：{exc}",
                code=50204,
            ) from exc
        except json.JSONDecodeError as exc:
            raise ErrorResponseAPIException(
                status_code=502,
                detail="AI 返回了无法解析的响应",
                code=50205,
            ) from exc

    def _build_authorization_header(self) -> str:
        authorization = (settings.TOKENHUB_AUTHORIZATION or "").strip()
        if authorization:
            return authorization

        api_key = (settings.TOKENHUB_API_KEY or "").strip()
        if not api_key:
            raise ErrorResponseAPIException(
                status_code=500,
                detail="未配置 AI 鉴权信息",
                code=50003,
            )

        if api_key.lower().startswith("bearer"):
            return api_key

        return f"Bearer {api_key}"
