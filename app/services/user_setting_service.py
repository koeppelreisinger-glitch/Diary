import uuid
import zoneinfo
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_setting import UserSetting
from app.schemas.user_setting import UserSettingsResponse, UpdateUserSettingsRequest
from app.core.exceptions import NotFoundException, ErrorResponseAPIException


class UserSettingService:
    """
    用户设置业务层处理逻辑
    包含：检索配置、受控更新配置
    """

    @staticmethod
    async def get_user_settings(session: AsyncSession, user_id: uuid.UUID) -> UserSettingsResponse:
        """
        获取当前登录用户的设置参数
        """
        stmt = select(UserSetting).where(
            UserSetting.user_id == user_id, 
            UserSetting.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        # 遵循 MVP 定向规则：如果没有记录就直接抛异常，不再此处静默创建
        if not setting:
            raise NotFoundException(detail="当前用户的配置记录不存在")
            
        return UserSettingsResponse.model_validate(setting)

    @staticmethod
    async def update_user_settings(
        session: AsyncSession, 
        user_id: uuid.UUID, 
        data: UpdateUserSettingsRequest
    ) -> UserSettingsResponse:
        """
        处理修改用户配置设定
        实现基于 Pydantic Partial 参数的有状态过滤更新以及交叉关联校验
        """
        stmt = select(UserSetting).where(
            UserSetting.user_id == user_id, 
            UserSetting.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        
        if not setting:
            raise NotFoundException(detail="当前用户的配置记录不存在，请确保已初始化关联")

        updated = False
        update_data = data.model_dump(exclude_unset=True)

        # 1. 更新与校验 时区 (timezone) 
        if "timezone" in update_data and update_data["timezone"] is not None:
            tz = update_data["timezone"]
            try:
                zoneinfo.ZoneInfo(tz)  # Python 3.9+ 内置对 IANA 全时区库合法性检验
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                raise ErrorResponseAPIException(
                    status_code=400, 
                    detail=f"非法时区标识：{tz}", 
                    code=40001
                )
            setting.timezone = tz
            updated = True

        # 2. 更新与校验 输入偏好 (input_preference)
        if "input_preference" in update_data and update_data["input_preference"] is not None:
            pref = update_data["input_preference"]
            # 配合底层文档防线冗余判断
            if pref not in ("text", "voice", "mixed"):
                raise ErrorResponseAPIException(
                    status_code=400, 
                    detail="输入偏好限制指定为 text / voice / mixed",
                    code=40001
                )
            setting.input_preference = pref
            updated = True
            
        # 3. 更新 提醒主开关 (reminder_enabled)
        if "reminder_enabled" in update_data:
            setting.reminder_enabled = update_data["reminder_enabled"]
            updated = True
            
        # 4. 更新 提醒时间表 (reminder_time)
        if "reminder_time" in update_data:
            time_str = update_data["reminder_time"]
            if time_str is None:
                setting.reminder_time = None
            else:
                try:
                    # 转化为 SQLAlchemy 支持落地的 datetime.time() 对象
                    setting.reminder_time = datetime.strptime(time_str, "%H:%M").time()
                except ValueError:
                    raise ErrorResponseAPIException(
                        status_code=400, 
                        detail="非法的 reminder_time 格式，应当为 HH:MM"
                    )
            updated = True

        # 5. 横跨字段核心业务判定（非常关键的联动状态检查）：
        # 如果提醒当前被确立为 True，那么库中（可能是当前旧存在或者正在更新后）的 reminder_time 必须有实际合法值支撑。
        if setting.reminder_enabled and not setting.reminder_time:
            raise ErrorResponseAPIException(
                status_code=400, 
                detail="开启每日提醒时，必须设定有效的每日提醒时间（reminder_time）",
                code=40002
            )
        
        # 6. 显式控制事务
        if updated:
            try:
                await session.commit()
                await session.refresh(setting)
            except Exception:
                await session.rollback()
                raise

        return UserSettingsResponse.model_validate(setting)
