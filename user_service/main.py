import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt, JWTError
from fastapi.middleware.cors import CORSMiddleware

# 导入我们刚才写的模块
import models
import schemas
from database import engine, get_db

# 1. 自动在 MySQL 中创建表 (生产环境通常用 Alembic 迁移，作业里这样写最快)
models.Base.metadata.create_all(bind=engine)

# 2. 初始化 FastAPI 应用
app = FastAPI(title="用户服务 (User Service)", version="1.0.0")

# 4. JWT 配置 (从环境变量读取)
SECRET_KEY = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "fallback_secret_key_for_dev"
)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))


# ================= 辅助函数 =================
def get_password_hash(password: str) -> str:
    """将明文密码加密为哈希值"""
    # bcrypt 规定密码必须是 bytes 类型，所以先 encode("utf-8")
    # gensalt() 会自动生成一个安全的随机盐值
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # 最后存入数据库的是字符串，所以再 decode 回去
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码和数据库里的哈希值是否匹配"""
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)


def create_access_token(data: dict):
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ================= 新增：配置跨域资源共享 (CORS) =================
app.add_middleware(
    CORSMiddleware,
    # 允许的跨域来源，开发阶段为了方便先写 "*" (允许所有)，生产环境要改成前端的真实域名
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], # 允许所有的 HTTP 方法 (GET, POST 等)
    allow_headers=["*"], # 允许所有的请求头
)
# =========================================================

# ================= API 路由接口 =================

@app.post("/api/users/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """用户注册接口"""
    # 1. 检查用户名是否已存在
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已被注册")

    # 2. 密码加密存储
    hashed_password = get_password_hash(user.password)
    new_user = models.User(username=user.username, password_hash=hashed_password)

    # 3. 写入数据库
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # 刷新以获取数据库自增的 ID

    return new_user


@app.post("/api/users/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    """用户登录接口"""
    # 1. 在数据库中查找用户
    db_user = db.query(models.User).filter(models.User.username == user.username).first()

    # 2. 校验用户名和密码
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 校验通过，生成 JWT Token
    access_token = create_access_token(data={"sub": str(db_user.id), "username": db_user.username})

    return {"access_token": access_token, "token_type": "bearer"}
