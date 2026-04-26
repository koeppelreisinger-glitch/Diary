import json
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_record import DailyRecord

class ExportService:
    @staticmethod
    async def export_user_data_json(session: AsyncSession, user_id: uuid.UUID) -> str:
        """
        导出用户所有数据为 JSON 格式
        """
        stmt = (
            select(DailyRecord)
            .where(DailyRecord.user_id == user_id, DailyRecord.deleted_at.is_(None))
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.inspirations),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.expenses),
                selectinload(DailyRecord.images)
            )
            .order_by(DailyRecord.record_date.desc())
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        export_data = []
        for r in records:
            item = {
                "date": r.record_date.isoformat(),
                "summary": r.summary_text,
                "body": r.body_text,
                "emotion_score": r.emotion_score,
                "events": [
                    {
                        "content": e.content, 
                        "start_time": e.start_time.strftime("%H:%M") if e.start_time else None
                    } for e in r.events
                ],
                "inspirations": [{"content": i.content} for i in r.inspirations],
                "emotions": [{"label": em.label, "intensity": em.intensity} for em in r.emotions],
                "locations": [{"name": l.name} for l in r.locations],
                "expenses": [{"amount": ex.amount, "category": ex.category, "description": ex.description} for ex in r.expenses],
                "images": [img.image_url for img in r.images]
            }
            export_data.append(item)
            
        return json.dumps({
            "export_at": uuid.uuid4().hex, # 仅作标识
            "user_id": str(user_id),
            "records": export_data
        }, ensure_ascii=False, indent=2)

    @staticmethod
    async def export_user_data_markdown(session: AsyncSession, user_id: uuid.UUID) -> str:
        """
        导出用户所有数据为 Markdown 格式，适合阅读
        """
        stmt = (
            select(DailyRecord)
            .where(DailyRecord.user_id == user_id, DailyRecord.deleted_at.is_(None))
            .options(
                selectinload(DailyRecord.events),
                selectinload(DailyRecord.inspirations),
                selectinload(DailyRecord.emotions),
                selectinload(DailyRecord.locations),
                selectinload(DailyRecord.expenses)
            )
            .order_by(DailyRecord.record_date.desc())
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        md_lines = ["# Echo 日记数据导出\n"]
        for r in records:
            md_lines.append(f"## {r.record_date.isoformat()}")
            md_lines.append(f"**情绪指数**: {r.emotion_score}/100")
            md_lines.append(f"\n### 今日摘要\n{r.summary_text}")
            md_lines.append(f"\n### 日记正文\n{r.body_text}")
            
            if r.events:
                md_lines.append("\n### 重要事件")
                for e in r.events:
                    time_prefix = f"[{e.start_time.strftime('%H:%M')}] " if e.start_time else "- "
                    md_lines.append(f"{time_prefix}{e.content}")
            
            if r.expenses:
                md_lines.append("\n### 账单明细")
                for ex in r.expenses:
                    md_lines.append(f"- 【{ex.category}】{ex.amount}元: {ex.description or '无备注'}")
            
            md_lines.append("\n---\n")

        return "\n".join(md_lines)
