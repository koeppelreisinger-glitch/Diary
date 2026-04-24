import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Query, Path

from app.core.deps import SessionDep, CurrentUser
from app.core.exceptions import ErrorResponseAPIException
from app.schemas.common import ApiResponse
from app.schemas.media import (
    ImageUploadResponse, ImageItem,
    HistoryImagesResponse, OnThisDayImagesResponse,
)
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/upload", response_model=ApiResponse[ImageUploadResponse])
async def upload_image(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    conversation_id: Optional[uuid.UUID] = Query(None, description="关联对话 ID（可选）"),
):
    """上传图片，返回 URL 和 ID，发消息时携带 image_url 即可"""
    result = await MediaService.upload_image(
        session=session,
        user_id=current_user.id,
        file=file,
        conversation_id=conversation_id,
    )
    return ApiResponse(data=result)


@router.get("/on-this-day", response_model=ApiResponse[OnThisDayImagesResponse])
async def get_images_on_this_day(
    session: SessionDep,
    current_user: CurrentUser,
):
    """历史上今天（跨年同月日）的图片，用于回忆版块情感钩子"""
    result = await MediaService.get_images_on_this_day(
        session=session, user_id=current_user.id
    )
    return ApiResponse(data=result)


@router.get("/history", response_model=ApiResponse[HistoryImagesResponse])
async def get_history_images(
    session: SessionDep,
    current_user: CurrentUser,
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """历史图片流（按日期倒序分组），用于回忆版块胶卷/方格视图"""
    start, end = None, None
    for raw, target in [(start_date, "start"), (end_date, "end")]:
        if raw:
            try:
                d = datetime.strptime(raw, "%Y-%m-%d").date()
                if target == "start":
                    start = d
                else:
                    end = d
            except ValueError:
                raise ErrorResponseAPIException(422, f"{target}_date 格式错误，需为 YYYY-MM-DD", 40001)

    result = await MediaService.get_history_images(
        session=session, user_id=current_user.id,
        start_date=start, end_date=end,
        page=page, page_size=page_size,
    )
    return ApiResponse(data=result)


@router.get("/history/{record_date}", response_model=ApiResponse[list[ImageItem]])
async def get_images_by_date(
    session: SessionDep,
    current_user: CurrentUser,
    record_date: str = Path(..., description="日期 YYYY-MM-DD"),
):
    """指定日期的所有图片，用于书页视图单日详情"""
    try:
        d = datetime.strptime(record_date, "%Y-%m-%d").date()
    except ValueError:
        raise ErrorResponseAPIException(422, "日期格式错误，需为 YYYY-MM-DD", 40001)
    result = await MediaService.get_images_by_date(
        session=session, user_id=current_user.id, record_date=d
    )
    return ApiResponse(data=result)


@router.delete("/{image_id}", response_model=ApiResponse[None])
async def delete_image(
    session: SessionDep,
    current_user: CurrentUser,
    image_id: uuid.UUID = Path(...),
):
    """软删除图片（仅限本人）"""
    await MediaService.delete_image(
        session=session, user_id=current_user.id, image_id=image_id
    )
    return ApiResponse(data=None, message="已删除")
