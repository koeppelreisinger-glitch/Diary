import asyncio
import json
import logging
from typing import Any
from urllib import error, request

from app.core.config import settings
from app.core.exceptions import ErrorResponseAPIException

logger = logging.getLogger(__name__)


class TokenHubChatService:
    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> dict[str, Any]:
        payload = {
            "model": settings.TOKENHUB_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        return await asyncio.to_thread(self._post_chat_completion, payload)

    async def create_text_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> str:
        response_data = await self.create_chat_completion(messages, temperature=temperature)
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

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": self._build_authorization_header(),
            "Content-Type": "application/json",
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            settings.TOKENHUB_CHAT_COMPLETIONS_URL,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=settings.TOKENHUB_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            logger.error("TokenHub request failed: status=%s body=%s", exc.code, detail)
            raise ErrorResponseAPIException(
                status_code=502,
                detail=f"AI 请求失败，状态码 {exc.code}",
                code=50203,
            ) from exc
        except error.URLError as exc:
            raise ErrorResponseAPIException(
                status_code=502,
                detail=f"AI 网络请求失败：{exc.reason}",
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
