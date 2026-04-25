import uuid
import os
import json
import asyncio
import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select, func, desc, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.media import DailyRecordImage
from app.models.daily_record import DailyRecord
from app.models.base import utc_now
from app.core.exceptions import ErrorResponseAPIException
from app.schemas.media import (
    ImageUploadResponse, ImageItem, ImageWithDateGroup,
    HistoryImagesResponse, OnThisDayImagesResponse,
)

logger = logging.getLogger(__name__)

# 本地存储根目录：Vercel /var/task 只读，必须用 /tmp；本地开发用项目根/uploads/
_IS_VERCEL = bool(os.environ.get("VERCEL"))
if _IS_VERCEL:
    UPLOADS_DIR = "/tmp/uploads"  # Vercel serverless 唯一可写目录
else:
    UPLOADS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads"
    )
try:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
except OSError:
    pass  # 只读文件系统时跳过（Vercel /tmp 应该始终可写，保险处理）

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class MediaService:

    @staticmethod
    async def upload_image(
        session: AsyncSession,
        user_id: uuid.UUID,
        file: UploadFile,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> ImageUploadResponse:
        """上传图片：校验 → 保存本地 → 查找当日记录 → 写数据库"""

        if file.content_type not in ALLOWED_TYPES:
            raise ErrorResponseAPIException(400, "不支持的图片格式，仅支持 JPEG/PNG/WebP/GIF", 40002)

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise ErrorResponseAPIException(400, "图片大小不能超过 10MB", 40003)

        # 读取图片尺寸
        width, height = None, None
        try:
            from PIL import Image as PilImage
            import io
            pil_img = PilImage.open(io.BytesIO(content))
            width, height = pil_img.size
        except Exception:
            pass

        # 生成存储路径
        today = date.today()
        mime = file.content_type or "image/jpeg"
        ext = mime.split("/")[-1].replace("jpeg", "jpg")
        file_name = f"{uuid.uuid4().hex}.{ext}"
        user_dir = os.path.join(UPLOADS_DIR, str(user_id), str(today))
        try:
            os.makedirs(user_dir, exist_ok=True)
        except OSError:
            pass
        file_path = os.path.join(user_dir, file_name)

        # Vercel 环境下 /tmp 不对外提供 HTTP，暂存后 url 留空（后续接入云存储）
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except OSError:
            logger.warning("[MediaService] 无法写入文件系统（Vercel 只读），图片不持久化")

        storage_key = f"{user_id}/{today}/{file_name}"
        if _IS_VERCEL:
            url = ""  # Vercel 无持久化本地存储，URL 暂为空（可接入 S3/Cloudinary）
        else:
            url = f"/uploads/{storage_key}"

        # 查找当天的 DailyRecord（可选绑定）
        daily_record_id = None
        try:
            stmt = select(DailyRecord).where(
                DailyRecord.user_id == user_id,
                DailyRecord.record_date == today,
                DailyRecord.deleted_at.is_(None),
            )
            rec = (await session.execute(stmt)).scalar_one_or_none()
            if rec:
                daily_record_id = rec.id
        except Exception:
            pass

        img = DailyRecordImage(
            user_id=user_id,
            daily_record_id=daily_record_id,
            record_date=today,
            storage_key=storage_key,
            url=url,
            original_filename=file.filename,
            mime_type=mime,
            file_size=len(content),
            width=width,
            height=height,
            conversation_id=conversation_id,
        )
        session.add(img)
        await session.commit()
        await session.refresh(img)

        # 触发异步后台任务：缩略图 + 主色调 + AI Vision（不阻塞上传响应）
        asyncio.create_task(
            MediaService._async_process_image(img.id, content)
        )

        return ImageUploadResponse(
            id=img.id,
            url=img.url,
            thumbnail_url=None,
            width=width,
            height=height,
            file_size=len(content),
        )

    @staticmethod
    async def get_history_images(
        session: AsyncSession,
        user_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> HistoryImagesResponse:
        """按日期倒序分组返回图片流"""
        stmt = select(DailyRecordImage).where(
            DailyRecordImage.user_id == user_id,
            DailyRecordImage.deleted_at.is_(None),
        )
        if start_date:
            stmt = stmt.where(DailyRecordImage.record_date >= start_date)
        if end_date:
            stmt = stmt.where(DailyRecordImage.record_date <= end_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(
            desc(DailyRecordImage.record_date),
            desc(DailyRecordImage.created_at),
        ).offset((page - 1) * page_size).limit(page_size)
        imgs = (await session.execute(stmt)).scalars().all()

        groups: dict[date, list] = defaultdict(list)
        for img in imgs:
            groups[img.record_date].append(MediaService._to_item(img))

        items = [
            ImageWithDateGroup(record_date=d, images=lst)
            for d, lst in sorted(groups.items(), reverse=True)
        ]

        return HistoryImagesResponse(
            items=items, total=total, page=page,
            page_size=page_size, has_more=total > page * page_size,
        )

    @staticmethod
    async def get_images_by_date(
        session: AsyncSession,
        user_id: uuid.UUID,
        record_date: date,
    ) -> list[ImageItem]:
        stmt = select(DailyRecordImage).where(
            DailyRecordImage.user_id == user_id,
            DailyRecordImage.record_date == record_date,
            DailyRecordImage.deleted_at.is_(None),
        ).order_by(DailyRecordImage.created_at)
        imgs = (await session.execute(stmt)).scalars().all()
        return [MediaService._to_item(i) for i in imgs]

    @staticmethod
    async def get_images_on_this_day(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> OnThisDayImagesResponse:
        today = date.today()
        stmt = select(DailyRecordImage).where(
            DailyRecordImage.user_id == user_id,
            func.extract("month", DailyRecordImage.record_date) == today.month,
            func.extract("day", DailyRecordImage.record_date) == today.day,
            DailyRecordImage.deleted_at.is_(None),
        ).order_by(desc(DailyRecordImage.record_date))
        imgs = (await session.execute(stmt)).scalars().all()

        groups: dict[date, list] = defaultdict(list)
        for img in imgs:
            if img.record_date.year != today.year:  # 只返回历史年份
                groups[img.record_date].append(MediaService._to_item(img))

        items = [
            ImageWithDateGroup(record_date=d, images=lst)
            for d, lst in sorted(groups.items(), reverse=True)
        ]
        return OnThisDayImagesResponse(month=today.month, day=today.day, items=items)

    @staticmethod
    async def delete_image(
        session: AsyncSession,
        user_id: uuid.UUID,
        image_id: uuid.UUID,
    ) -> None:
        stmt = select(DailyRecordImage).where(DailyRecordImage.id == image_id)
        img = (await session.execute(stmt)).scalar_one_or_none()
        if not img:
            raise ErrorResponseAPIException(404, "图片不存在", 40401)
        if img.user_id != user_id:
            raise ErrorResponseAPIException(403, "无权删除此图片", 40301)
        img.deleted_at = utc_now()
        await session.commit()

    @staticmethod
    def _to_item(img: DailyRecordImage) -> ImageItem:
        ai_tags, ai_colors = None, None
        try:
            if img.ai_tags:
                ai_tags = json.loads(img.ai_tags)
        except Exception:
            pass
        try:
            if img.dominant_colors:
                ai_colors = json.loads(img.dominant_colors)
        except Exception:
            pass
        return ImageItem(
            id=img.id,
            record_date=img.record_date,
            url=img.url,
            thumbnail_url=img.thumbnail_url,
            ai_caption=img.ai_caption,
            ai_tags=ai_tags,
            dominant_colors=ai_colors,
            width=img.width,
            height=img.height,
            created_at=img.created_at,
        )

    # ── 异步后台处理 ─────────────────────────────────────────────

    @staticmethod
    async def _async_process_image(image_id: uuid.UUID, content: bytes) -> None:
        """
        图片上传完成后由 create_task 触发，完全不阻塞上传响应。

        doc14 §3.3 v1.1 优化：图像处理（步骤 1+2）与 AI Vision 调用（步骤 3）
        改为 asyncio.gather 并行执行，总耗时从「处理 + AI」变为 max(处理, AI) ≈ AI 时间。

        步骤 1+2：Pillow resize（缩略图）+ quantize（主色调，线程池执行）
        步骤 3：POST glm-5v-turbo，stream=false，response_format=json_object
        步骤 4：一次性写回 daily_record_images 表
        """
        import io as _io
        import base64
        import httpx
        from PIL import Image as PilImage

        try:
            pil_img = PilImage.open(_io.BytesIO(content)).convert("RGB")

            # ── 并行分支 A：图像处理（缩略图 + 主色调）─────────────────────

            async def _image_processing_task():
                """步骤 1+2：缩略图生成 + 主色提取（CPU 密集部分放线程池）"""
                # 步骤 1：生成 300px 宽缩略图
                t_w = 300
                t_h = max(1, int(pil_img.height * t_w / pil_img.width))
                thumb = pil_img.resize((t_w, t_h), PilImage.LANCZOS)
                buf = _io.BytesIO()
                thumb.save(buf, format="JPEG", quality=80)

                thumb_dir = os.path.join(UPLOADS_DIR, "thumbnails")
                os.makedirs(thumb_dir, exist_ok=True)
                with open(os.path.join(thumb_dir, f"{image_id}.jpg"), "wb") as fp:
                    fp.write(buf.getvalue())
                _thumb_url = f"/uploads/thumbnails/{image_id}.jpg"

                # 步骤 2：主色调提取（CPU 密集 → 线程池，不阻塞事件循环）
                ev_loop = asyncio.get_event_loop()
                _colors = await ev_loop.run_in_executor(
                    None, MediaService._extract_dominant_colors, pil_img
                )
                return _thumb_url, _colors

            # ── 并行分支 B：AI Vision 调用 ────────────────────────────────

            async def _ai_vision_task():
                """
                步骤 3：调用 AI Vision（stream=false，response_format=json_object）
                doc14 §3.3: 后台分析需要完整 JSON，非流式一次性拿到结果。
                """
                _url   = getattr(settings, "TOKENHUB_CHAT_COMPLETIONS_URL",
                                 "https://tokenhub.tencentmaas.com/v1/chat/completions")
                _auth  = (getattr(settings, "TOKENHUB_AUTHORIZATION", None) or
                          f"Bearer {getattr(settings, 'TOKENHUB_API_KEY', '')}")
                _model = getattr(settings, "TOKENHUB_MODEL", "glm-5v-turbo")

                _key = _auth.replace("Bearer ", "").strip()
                if not _key or _key in ("", "None"):
                    return None, None

                _b64 = base64.b64encode(content).decode()
                _payload = {
                    "model": _model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{_b64}",
                                    "detail": "low",
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "\u8bf7\u7528\u4e2d\u6587\u5206\u6790\u56fe\u7247"
                                    "\uff0c\u4e25\u683c\u6309 JSON \u8fd4\u56de"
                                    "\uff0c\u4e0d\u8981\u591a\u4f59\u6587\u5b57\uff1a"
                                    '{"caption":"\u4e00\u53e5\u8bdd\u63cf\u8ff0'
                                    '(\u226450\u5b57)","tags":["\u6807\u51711"'
                                    ',"\u6807\u51712","\u6807\u51713"]}'
                                ),
                            },
                        ],
                    }],
                    "stream": False,
                    "max_tokens": 200,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},  # doc14 §3.3: 强制合法 JSON
                }
                _headers = {
                    "Authorization": _auth if _auth.startswith("Bearer ") else f"Bearer {_auth}",
                    "Content-Type": "application/json",
                }
                try:
                    async with httpx.AsyncClient(timeout=20.0) as _client:
                        _resp = await _client.post(_url, headers=_headers, json=_payload)
                        if _resp.status_code == 200:
                            _raw = _resp.json()["choices"][0]["message"]["content"]
                            _parsed = json.loads(_raw)
                            return (
                                _parsed.get("caption"),
                                json.dumps(_parsed.get("tags", []), ensure_ascii=False),
                            )
                except Exception as _ai_exc:
                    logger.warning(
                        "[MediaService] AI Vision 调用失败 image_id=%s: %s", image_id, _ai_exc
                    )
                return None, None

            # ── 并行执行：总耗时 = max(图像处理时间, AI Vision 时间) ────────
            (thumbnail_url, dominant_colors), (ai_caption, ai_tags) = await asyncio.gather(
                _image_processing_task(),
                _ai_vision_task(),
            )

            # ── 步骤 4：一次性写回数据库（独立会话，不使用传入的请求 session）─
            async with AsyncSessionLocal() as db:
                await db.execute(
                    sa_update(DailyRecordImage)
                    .where(DailyRecordImage.id == image_id)
                    .values(
                        thumbnail_url=thumbnail_url,
                        ai_caption=ai_caption,
                        ai_tags=ai_tags,
                        dominant_colors=json.dumps(dominant_colors, ensure_ascii=False),
                    )
                )
                await db.commit()

        except Exception as exc:
            logger.error("[MediaService] 图片异步处理失败 image_id=%s: %s", image_id, exc)
            # 字段保持 NULL，不影响用户侧功能

    @staticmethod
    def _extract_dominant_colors(img, n: int = 3) -> list:
        """提取图片前 n 个主色，返回 hex 列表，如 ['#F5D76E', '#8B4513']。"""
        try:
            small     = img.resize((100, 100))
            quantized = small.quantize(colors=n * 3, method=2).convert("RGB")
            palette   = sorted(quantized.getcolors(10000) or [], key=lambda x: x[0], reverse=True)
            seen, result = set(), []
            for _, rgb in palette:
                h = "#{:02X}{:02X}{:02X}".format(*rgb)
                if h not in seen:
                    seen.add(h)
                    result.append(h)
                if len(result) >= n:
                    break
            return result
        except Exception:
            return []
