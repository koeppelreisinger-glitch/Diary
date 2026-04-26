import uuid
from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utc_now
from app.models.user import User
from app.models.user_setting import UserSetting
from app.models.daily_record import DailyRecord, RecordEvent
from app.schemas.auth import RegisterRequest, LoginRequest, LoginResponse
from app.schemas.user import CurrentUserResponse, UpdateUserRequest, UserStatsResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.core.exceptions import ConflictException, CredentialsException, ForbiddenException


def mask_phone_number(phone: str) -> str:
    """脱敏手机号：保留前 3 位和后 4 位，其余替换为 *"""
    if not phone:
        return phone
    # 如果短于 7 位做保守脱敏
    if len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"


class AuthService:
    """
    用户鉴权与基础档案体系相关服务逻辑
    包含：注册、登录、查询本身、局部更新
    """

    @staticmethod
    async def register_user(session: AsyncSession, data: RegisterRequest) -> CurrentUserResponse:
        """
        处理用户注册逻辑
        """
        # 1. 检查手机号是否存在
        stmt = select(User).where(User.phone == data.phone, User.deleted_at.is_(None))
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictException(detail="该手机号已被注册")

        # 2. 显式包裹级联落盘防止事务外泄
        try:
            new_user = User(
                phone=data.phone,
                hashed_password=hash_password(data.password),
                nickname=data.nickname or f"回响_{uuid.uuid4().hex[:6]}",
                status="active"
            )
            session.add(new_user)
            await session.flush()

            new_setting = UserSetting(
                user_id=new_user.id,
                timezone="UTC",
                input_preference="mixed",
                is_dark_mode=False
            )
            session.add(new_setting)

            await session.commit()
            await session.refresh(new_user)
            return AuthService.get_current_user_profile(new_user)
        
        except Exception:
            await session.rollback()
            raise


    @staticmethod
    async def login_user(session: AsyncSession, data: LoginRequest) -> LoginResponse:
        """
        处理用户登录逻辑
        """
        # 1. 查询用户
        stmt = select(User).where(User.phone == data.phone, User.deleted_at.is_(None))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        # 2. 账号存在性与凭证校验（防暴露）
        if not user or not verify_password(data.password, user.hashed_password):
            raise CredentialsException(detail="手机号或密码不正确")

        # 3. 校验账号启用状态
        if user.status != "active":
            raise ForbiddenException(detail="账号已被禁用")

        # 4. 更新业务审计信息并提交
        try:
            user.last_login_at = utc_now()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        # 5. 颁发 JWT Access Token
        access_token = create_access_token(subject=user.id)
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in
        )


    @staticmethod
    def get_current_user_profile(user: User) -> CurrentUserResponse:
        """
        显式构造用户信息结构，从而彻底隔离源 ORM 后续覆写污染并安全脱敏
        """
        return CurrentUserResponse(
            id=user.id,
            phone=mask_phone_number(user.phone),
            email=user.email,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        )


    @staticmethod
    async def update_user_profile(session: AsyncSession, user: User, data: UpdateUserRequest) -> CurrentUserResponse:
        """
        更新当前用户基础信息的范围受控方法
        """
        updated = False
        update_data = data.model_dump(exclude_unset=True)
        
        # 处理 nickname (不允许清空设 null)
        if "nickname" in update_data and update_data["nickname"] is not None:
            user.nickname = update_data["nickname"]
            updated = True
        
        # 处理 avatar_url (允许传 null 清空)
        if "avatar_url" in update_data:
            user.avatar_url = update_data["avatar_url"]
            updated = True

        if updated:
            try:
                await session.commit()
                await session.refresh(user)
            except Exception:
                await session.rollback()
                raise

        return AuthService.get_current_user_profile(user)


    @staticmethod
    async def get_user_stats(session: AsyncSession, user: User) -> UserStatsResponse:
        """
        计算用户统计数据：总记录天数、连续打卡、总事件数
        """
        # 1. 总记录天数
        total_days_res = await session.execute(
            select(func.count(DailyRecord.id)).where(
                DailyRecord.user_id == user.id,
                DailyRecord.deleted_at.is_(None)
            )
        )
        total_days = total_days_res.scalar() or 0

        # 2. 总事件数
        total_events_res = await session.execute(
            select(func.count(RecordEvent.id)).where(
                RecordEvent.user_id == user.id,
                RecordEvent.deleted_at.is_(None)
            )
        )
        total_events = total_events_res.scalar() or 0

        # 3. 连续打卡：取近 365 天的记录日期，倒序排列后逐天比对
        dates_res = await session.execute(
            select(DailyRecord.record_date)
            .where(
                DailyRecord.user_id == user.id,
                DailyRecord.deleted_at.is_(None)
            )
            .order_by(DailyRecord.record_date.desc())
            .limit(365)
        )
        dates = [row[0] for row in dates_res.fetchall()]

        streak = 0
        today = date.today()
        # 允许当天未记录时从昨天开始算
        expected = today if (dates and dates[0] == today) else today - timedelta(days=1)
        for d in dates:
            if d == expected:
                streak += 1
                expected = expected - timedelta(days=1)
            elif d < expected:
                break  # 日期不连续，停止
            # d > expected means future date somehow, skip

        return UserStatsResponse(
            total_days=total_days,
            current_streak=streak,
            total_events=total_events
        )
