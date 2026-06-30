"""认证路由：登录、刷新 Token、查看当前用户。"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import settings
from ..models.schemas import SuccessResponse
from ..security.auth import AuthUser, create_jwt_token, get_current_user, is_auth_enabled

router = APIRouter()


class DemoLoginRequest(BaseModel):
    role: str


class PasswordLoginRequest(BaseModel):
    username: str
    password: str


DEMO_ROLES = {"admin", "analyst", "support"}


@router.get("/api/auth/status")
async def auth_status():
    return {
        "auth_enabled": is_auth_enabled(),
        "methods": ["jwt", "api_key"] if is_auth_enabled() else [],
    }


@router.post("/api/auth/demo-login")
async def demo_login(request: DemoLoginRequest):
    if not settings.AUTH_DEMO_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="演示登录未启用")

    role = request.role.strip().lower()
    if role not in DEMO_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的演示角色")

    try:
        token_data = create_jwt_token(user_id=f"demo:{role}", roles=[role])
    except HTTPException as exc:
        if exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT_SECRET 未配置，无法启用本地演示登录",
            ) from exc
        raise

    # 只返回最小身份摘要，让前端能演示权限闭环，同时不暴露密钥或完整权限策略。
    user = {"user_id": f"demo:{role}", "auth_method": "jwt", "roles": [role]}
    return SuccessResponse(code=200, message="demo login success", data={**token_data, "user": user})


@router.post("/api/auth/login")
async def login(request: PasswordLoginRequest):
    if not settings.AUTH_PASSWORD_LOGIN_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="密码登录未启用")

    if not settings.AUTH_ADMIN_USERNAME or not settings.AUTH_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理员账号未配置，无法启用密码登录",
        )

    if request.username == settings.AUTH_ADMIN_USERNAME and request.password == settings.AUTH_ADMIN_PASSWORD:
        try:
            token_data = create_jwt_token(user_id=request.username, roles=["admin", "user"])
        except HTTPException as exc:
            if exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="JWT_SECRET 未配置，无法启用密码登录",
                ) from exc
            raise
        return SuccessResponse(code=200, message="登录成功", data=token_data)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户名或密码错误",
    )


@router.get("/api/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    if user is None:
        return {"user_id": "anonymous", "auth_method": "none", "roles": ["guest"]}
    return {"user_id": user.user_id, "auth_method": user.auth_method, "roles": user.roles}
