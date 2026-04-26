import json
import logging
import re
from typing import Any, Iterable

from app.core.config import settings
from app.models.conversation import ConversationMessage
from app.services.tokenhub_chat_service import TokenHubChatService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 全局提示词常量
# ─────────────────────────────────────────────────────────────────────────────

_ANALYSIS_SYSTEM_PROMPT = """你是「Echo 日记」AI分析引擎。基于对话或正文提取结构化日记数据，只输出JSON，不加Markdown或解释。

字段规范：
- events: 每条一个真实事件，≤30字，合并重复
- emotions: emotion_label为2-4字中文情绪词（开心/焦虑/疲惫/平静等），intensity为1-5整数（1弱5强），不重复
- expenses: 有明确金额才记，amount为数字，currency默认CNY，category简短中文（餐饮/交通/购物/娱乐/其他）
- locations: 只记明确提到的真实地点，用具体名称而非泛称
- inspirations: 1-5条用户该天的灵感或感惟，每条不超过20字，用自然语言记录""

_FROM_MESSAGES_USER_TEMPLATE = """\
请分析以下对话，生成日记数据，严格按照 JSON 格式输出：
{{
  "body_text": "（用第一人称自然语言写的完整日记，时间顺序，包含所有对话中提到的关键事件、情绪和细节，结尾加一句总结，不少于100字）",
  "summary_text": "（一句话概括今天，50字以内，适合展示在列表中）",
  "emotion_overall_score": （今天整体情绪分，1-10的整数，1=极差，10=极好）,
  "keywords": ["关键词1", "关键词2", "...（最多8个）"],
  "events": [{{"content": "事件描述（简洁、包含核心信息，不超过30字）"}}],
  "emotions": [{{"emotion_label": "情绪描述", "intensity": （1-5整数）}}],
  "expenses": [{{"amount": （数字）, "currency": "CNY", "category": "分类", "description": "具体内容"}}],
  "locations": [{{"name": "完整真实地点名称"}}],
  "inspirations": [{{"content": "用户该天的一奇想法、感惟或发现，不超过20字"}}]
}}

对话记录：
{conversation}"""

_FROM_BODY_TEXT_USER_TEMPLATE = """\
请分析以下日记正文，提取结构化数据，严格按照 JSON 格式输出：
{{
  "summary_text": "（一句话概括今天，50字以内，适合展示在列表中）",
  "emotion_overall_score": （今天整体情绪分，1-10的整数）,
  "keywords": ["关键词1", "关键词2", "...（最多8个）"],
  "events": [{{"content": "事件描述（简洁、包含核心信息，不超过30字）"}}],
  "emotions": [{{"emotion_label": "情绪描述", "intensity": （1-5整数）}}],
  "expenses": [{{"amount": （数字，必须精确）, "currency": "CNY", "category": "分类", "description": "具体内容"}}],
  "locations": [{{"name": "完整真实地点名称"}}],
  "inspirations": [{{"content": "用户该天的一奇想法、感惟或发现，不超过20字"}}]
}}

注意：body_text 字段无需输出（原文已有），请忠实于原文，不编造。

日记正文：
{body_text}"""


class DiaryAIService:
    async def build_record_payload_from_messages(
        self,
        messages: list[ConversationMessage],
    ) -> dict[str, Any]:
        """通过完整对话生成日记 payload（含 body_text、结构化五表）。"""
        conversation_text = self._serialize_conversation(messages)
        user_content = _FROM_MESSAGES_USER_TEMPLATE.format(conversation=conversation_text)

        chat_messages = [
            {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        logger.info(
            "DiaryAIService.build_record_payload_from_messages: calling %s (model=%s, msg_count=%d)",
            settings.TOKENHUB_CHAT_COMPLETIONS_URL,
            settings.TOKENHUB_MODEL,
            len(messages),
        )

        response_text = await TokenHubChatService().create_text_completion(
            chat_messages,
            temperature=settings.TOKENHUB_SUMMARY_TEMPERATURE,
            response_format={"type": "json_object"},  # doc14 §3.4.2: 强制合法 JSON
        )

        logger.info(
            "DiaryAIService.build_record_payload_from_messages: AI returned %d chars",
            len(response_text),
        )

        parsed = self._parse_json_text(response_text)
        return self._normalize_record_payload(parsed, fallback_text=self._join_user_messages(messages))

    async def build_record_payload_from_body_text(self, body_text: str) -> dict[str, Any]:
        """通过已有正文重新提取结构化五表（Path A 重建场景）。"""
        user_content = _FROM_BODY_TEXT_USER_TEMPLATE.format(body_text=body_text)

        chat_messages = [
            {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        logger.info(
            "DiaryAIService.build_record_payload_from_body_text: calling %s (model=%s, body_len=%d)",
            settings.TOKENHUB_CHAT_COMPLETIONS_URL,
            settings.TOKENHUB_MODEL,
            len(body_text),
        )

        response_text = await TokenHubChatService().create_text_completion(
            chat_messages,
            temperature=settings.TOKENHUB_SUMMARY_TEMPERATURE,
            response_format={"type": "json_object"},  # doc14 §3.4.2: 强制合法 JSON
        )

        logger.info(
            "DiaryAIService.build_record_payload_from_body_text: AI returned %d chars",
            len(response_text),
        )

        parsed = self._parse_json_text(response_text)
        normalized = self._normalize_record_payload(parsed, fallback_text=body_text)
        # body_text 由用户提供，保持原文不替换
        normalized["body_text"] = body_text.strip()
        return normalized

    # ─── Fallback（无 AI 时使用简单规则兜底） ───────────────────────────────

    def build_record_payload_from_messages_fallback(
        self,
        messages: list[ConversationMessage],
    ) -> dict[str, Any]:
        logger.warning("DiaryAIService: using LOCAL FALLBACK (no AI) for messages payload")
        user_text = self._join_user_messages(messages)
        body_text = self._fallback_body_text(user_text)
        return self.build_record_payload_from_body_text_fallback(body_text)

    def build_record_payload_from_body_text_fallback(self, body_text: str) -> dict[str, Any]:
        logger.warning("DiaryAIService: using LOCAL FALLBACK (no AI) for body_text payload")
        text = body_text.strip()
        keywords = self._fallback_keywords(text)
        payload = {
            "body_text": text or "今天过得比较平静，我先把这一天留在这里，等之后再慢慢补充。",
            "summary_text": self._fallback_summary(text),
            "emotion_overall_score": self._fallback_emotion_score(text),
            "keywords": keywords,
            "events": self._fallback_events(text),
            "emotions": self._fallback_emotions(text),
            "expenses": self._fallback_expenses(text),
            "locations": self._fallback_locations(text),
            "inspirations": self._fallback_inspirations(text, keywords),
        }
        return self._normalize_record_payload(payload, fallback_text=text)

    # ─── 序列化与解析 ────────────────────────────────────────────────────────

    def _serialize_conversation(self, messages: list[ConversationMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            role = "AI助手" if message.role == "ai" else "用户"
            content = (message.content or "").strip()
            if not content:
                continue
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    def _join_user_messages(self, messages: list[ConversationMessage]) -> str:
        return "\n".join(
            (message.content or "").strip()
            for message in messages
            if message.role == "user" and (message.content or "").strip()
        ).strip()

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        """解析 AI 返回的 JSON 文本，支持多种格式。"""
        cleaned = text.strip()

        # 去除 markdown 代码块
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```\s*$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试从文本中提取第一个花括号包裹的 JSON 对象
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                logger.error("DiaryAIService._parse_json_text: no JSON found in response. raw=%r", text[:500])
                raise ValueError(f"AI 返回内容中未找到有效 JSON。原始内容片段：{text[:200]}")
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                logger.error("DiaryAIService._parse_json_text: regex-extracted JSON is invalid. raw=%r", text[:500])
                raise ValueError(f"AI 返回的 JSON 格式无效：{exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI 返回的 JSON 必须是对象（dict），实际为其他类型")

        return parsed

    # ─── Payload 规范化 ──────────────────────────────────────────────────────

    def _normalize_record_payload(self, payload: dict[str, Any], fallback_text: str) -> dict[str, Any]:
        body_text = str(payload.get("body_text") or fallback_text or "").strip()
        if not body_text:
            body_text = "今天过得比较平静，我先把这一天留在这里，等之后再慢慢补充。"

        summary_text = str(payload.get("summary_text") or "").strip() or self._fallback_summary(body_text)
        emotion_overall_score = self._clamp_int(
            payload.get("emotion_overall_score"), minimum=1, maximum=10,
            default=self._fallback_emotion_score(body_text)
        )
        keywords = self._normalize_string_list(payload.get("keywords"), max_items=8) or self._fallback_keywords(body_text)
        events = self._normalize_events(payload.get("events"))
        emotions = self._normalize_emotions(payload.get("emotions"))
        expenses = self._normalize_expenses(payload.get("expenses"))
        locations = self._normalize_locations(payload.get("locations"))
        inspirations = self._normalize_inspirations(payload.get("inspirations"))

        return {
            "body_text": body_text,
            "summary_text": summary_text,
            "emotion_overall_score": emotion_overall_score,
            "keywords": keywords,
            "events": events,
            "emotions": emotions,
            "expenses": expenses,
            "locations": locations,
            "inspirations": inspirations,
        }

    def _normalize_events(self, raw: Any) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for item in self._iter_list(raw):
            if isinstance(item, dict):
                content = str(item.get("content") or "").strip()
            else:
                content = str(item).strip()
            if content:
                items.append({"content": content})
        return items[:15]

    def _normalize_emotions(self, raw: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in self._iter_list(raw):
            if not isinstance(item, dict):
                continue
            emotion_label = str(item.get("emotion_label") or "").strip()
            intensity = self._clamp_int(item.get("intensity"), minimum=1, maximum=5, default=3)
            if emotion_label:
                items.append({"emotion_label": emotion_label, "intensity": intensity})
        return items[:10]

    def _normalize_expenses(self, raw: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in self._iter_list(raw):
            if not isinstance(item, dict):
                continue
            amount = self._to_float(item.get("amount"))
            if amount is None or amount < 0:
                continue
            currency = str(item.get("currency") or "CNY").strip() or "CNY"
            category = self._optional_string(item.get("category"))
            description = self._optional_string(item.get("description"))
            items.append({
                "amount": round(amount, 2),
                "currency": currency,
                "category": category,
                "description": description,
            })
        return items[:20]

    def _normalize_locations(self, raw: Any) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for item in self._iter_list(raw):
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(item).strip()
            if name:
                items.append({"name": name})
        return items[:15]

    def _normalize_inspirations(self, raw: Any) -> list[dict[str, str]]:
        names = self._normalize_string_list(
            [item.get("content") if isinstance(item, dict) else item for item in self._iter_list(raw)],
            max_items=5,
        )
        return [{"content": name} for name in names]

    def _normalize_string_list(self, raw: Any, *, max_items: int) -> list[str]:
        seen: set[str] = set()
        values: list[str] = []
        for item in self._iter_list(raw):
            value = str(item or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value)
            if len(values) >= max_items:
                break
        return values

    def _iter_list(self, raw: Any) -> Iterable[Any]:
        if isinstance(raw, list):
            return raw
        return []

    def _optional_string(self, value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    def _clamp_int(self, value: Any, *, minimum: int, maximum: int, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(minimum, min(maximum, number))

    def _to_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ─── Fallback 规则生成（无 AI 时使用） ──────────────────────────────────

    def _fallback_body_text(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return "今天过得比较平静，我先把这一天留在这里，等之后再慢慢补充。"
        return stripped

    def _fallback_summary(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return "今天整体比较平静，暂时没有特别明确的记录内容。"
        return stripped[:80] + ("..." if len(stripped) > 80 else "")

    def _fallback_emotion_score(self, text: str) -> int:
        if any(keyword in text for keyword in ["累", "疲惫", "焦虑", "烦"]):
            return 4
        if any(keyword in text for keyword in ["开心", "高兴", "轻松", "满足"]):
            return 8
        return 6

    def _fallback_keywords(self, text: str) -> list[str]:
        keywords: list[str] = []
        mapping = [
            ("工作", ["工作", "开会", "客户", "上班"]),
            ("社交", ["朋友", "同事", "家人", "聚会"]),
            ("消费", ["咖啡", "奶茶", "外卖", "打车", "花了", "元"]),
            ("疲惫", ["累", "疲惫", "心累"]),
            ("开心", ["开心", "高兴", "满足"]),
        ]
        for label, needles in mapping:
            if any(needle in text for needle in needles):
                keywords.append(label)
        return keywords or ["日常记录"]

    def _fallback_events(self, text: str) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        for sentence in re.split(r"[。！？\n]", text):
            sentence = sentence.strip()
            if len(sentence) >= 6:
                events.append({"content": sentence[:30]})
            if len(events) >= 5:
                break
        return events

    def _fallback_emotions(self, text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        mapping = [
            ("疲惫", ["累", "疲惫", "心累"], 4),
            ("开心", ["开心", "高兴", "满足"], 4),
            ("焦虑", ["焦虑", "烦", "紧张"], 3),
        ]
        for label, needles, intensity in mapping:
            if any(needle in text for needle in needles):
                items.append({"emotion_label": label, "intensity": intensity})
        return items[:5]

    def _fallback_expenses(self, text: str) -> list[dict[str, Any]]:
        pattern = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*元")
        items: list[dict[str, Any]] = []
        for match in pattern.finditer(text):
            amount = float(match.group("amount"))
            items.append({
                "amount": round(amount, 2),
                "currency": "CNY",
                "category": "消费",
                "description": "文本中提到的一笔支出",
            })
            if len(items) >= 5:
                break
        return items

    def _fallback_locations(self, text: str) -> list[dict[str, str]]:
        candidates = ["公司", "办公室", "家", "学校", "咖啡店", "商场", "地铁站"]
        return [{"name": name} for name in candidates if name in text][:5]

    def _fallback_inspirations(self, text: str, keywords: list[str]) -> list[dict[str, str]]:
        inspirations: list[str] = []
        if any(word in text for word in ["朋友", "聚会", "聊天"]):
            inspirations.append("和朋友在一起的时间总是很治愈")
        if any(word in text for word in ["工作", "开会", "客户"]):
            inspirations.append("工作虽忙，但这就是我正在路上的证明")
        normalized = self._normalize_string_list(inspirations, max_items=3)
        return [{"content": c} for c in normalized]
