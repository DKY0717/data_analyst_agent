"""认证路由：登录、刷新 Token、查看当前用户。"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.schemas import SuccessResponse
from ..security.auth import AuthUser, create_jwt_token, get_current_user, is_auth_enabled

router = APIRouter()


@router.get("/api/auth/status")
async def auth_status():
    return {
        "auth_enabled": is_auth_enabled(),
        "methods": ["jwt", "api_key"] if is_auth_enabled() else [],
    }


@router.post("/api/auth/login")
async def login(username: str, password: str):
    admin_user = "admin"
    admin_pass = "admin123"

    if username == admin_user and password == admin_pass:
        token_data = create_jwt_token(user_id=username, roles=["admin", "user"])
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
