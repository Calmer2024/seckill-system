from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

# ================= 共享的基础模型 =================
class UserBase(BaseModel):
    # Field 用于定义详细的校验规则
    username: str = Field(..., min_length=3, max_length=50, description="用户名，3-50个字符")

# ================= 请求模型 (前端发给后端的) =================
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="密码，至少6位")

class UserLogin(UserBase):
    password: str

# ================= 响应模型 (后端返回给前端的) =================
class UserResponse(UserBase):
    id: int
    created_at: datetime

    # 关键配置：让 Pydantic 能够读取 SQLAlchemy 的 ORM 模型数据
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"