from typing import List

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Echo AI Backend"
    VERSION: str = "0.1.0-MVP"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "REPLACE_THIS_WITH_A_SECURE_SECRET_KEY"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    DATABASE_URL: str | None = None  # 优先：完整连接串（Vercel / 云数据库场景）

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "echo_db"
    POSTGRES_PORT: int = 5432

    TOKENHUB_CHAT_COMPLETIONS_URL: str = "https://tokenhub.tencentmaas.com/v1/chat/completions"
    TOKENHUB_AUTHORIZATION: str | None = None
    TOKENHUB_API_KEY: str | None = None
    TOKENHUB_MODEL: str = "glm-4-flash"
    TOKENHUB_CHAT_SYSTEM_PROMPT: str = (
        "你是「Echo」，用户的日记伙伴，帮他把这一天的事情记下来。\n"
        "【性格】像温暖有趣的老朋友，语气随和，可用语气词，偶尔加冷知识或轻松幽默。\n"
        "【提问策略】引导用户说出：关键事件、情绪感受、消费金额、具体地点、灵感感悟。信息不全时精准追问（如：具体花了多少？在哪儿？心情如何？）。一次只提一个问题。\n"
        "【节奏】每次只问一个问题。先一句接住情绪再推进。不列清单不编号。用户回复字数少于等于两个字时换话题，最多换2次。\n"
        "【重要限制】每次回复必须极其精简，字数严格控制在 30 字以内。"
    )
    TOKENHUB_RECORD_SYSTEM_PROMPT: str = (
        "你是 Echo 日记总结引擎。基于对话生成正文摘要和结构化信息，正文为自然流畅的中文日记（含末尾总结），摘要简洁适合列表展示。"
        "必须把用户的零散回答、短句、地点、金额、确认语消化成通顺叙述，不能逐字粘贴聊天记录，不能把用户回答按行追加到正文末尾。"
        "只输出 JSON，不输出 Markdown。"
    )
    TOKENHUB_REBUILD_SYSTEM_PROMPT: str = (
        "你是 Echo 日记重建引擎。基于日记正文重新提取摘要和结构化信息，忠于原文不虚构。"
        "每次重建调整叙述方式（换句式开头、换词、调整节奏、末尾总结句不同），让文字更鲜活。"
        "summary_text 每次略有不同。只输出 JSON。"
    )
    TOKENHUB_TEMPERATURE: float = 0.7
    TOKENHUB_SUMMARY_TEMPERATURE: float = 0.3
    TOKENHUB_TIMEOUT_SECONDS: int = 90  # glm-5 单次调用最长等待时间（秒）

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        import os
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        # pydantic-settings 在某些 PaaS 上读不到 env，直接用 os.environ 保底
        raw = self.DATABASE_URL or os.environ.get("DATABASE_URL")
        if raw:
            url = raw.strip()

            # 统一驱动前缀为 asyncpg
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

            # 去掉 asyncpg 不能识别的 query 参数
            # SSL 改由 database.py 的 connect_args={"ssl": ssl_context} 处理
            parsed = urlparse(url)
            params = parse_qs(parsed.query, keep_blank_values=False)
            params.pop("sslmode", None)
            params.pop("ssl", None)
            params.pop("channel_binding", None)

            new_query = urlencode({k: v[0] for k, v in params.items()})
            url = urlunparse(parsed._replace(query=new_query))
            return url

        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
