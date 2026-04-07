from dataclasses import dataclass

from fastapi import Header
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions.business_exception import BusinessException


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    username: str | None = None


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: int | None = Header(default=None),
) -> CurrentUser:
    if x_user_id:
        return CurrentUser(user_id=x_user_id)

    if not authorization or not authorization.startswith("Bearer "):
        raise BusinessException(
            code="UNAUTHORIZED",
            message="请先登录后再参与秒杀",
            status_code=401,
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise BusinessException(
            code="INVALID_TOKEN",
            message="登录状态已失效，请重新登录",
            status_code=401,
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise BusinessException(
            code="INVALID_TOKEN",
            message="登录状态已失效，请重新登录",
            status_code=401,
        )

    return CurrentUser(user_id=int(subject), username=payload.get("username"))
