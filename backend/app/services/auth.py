# backend/app/services/auth.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.models import User

# Конфігурація JWT
SECRET_KEY = "CHANGE_THIS_TO_A_VERY_SECRET_KEY_IN_PRODUCTION" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Новий клас виключення для неавторизованих користувачів
class NotAuthenticatedException(Exception):
    pass

# Хешування та перевірка паролів
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Робота з токенами
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Залежність для отримання поточного користувача
def get_token_from_request(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    return token

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    
    if not token:
        raise NotAuthenticatedException()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise NotAuthenticatedException()
    except JWTError:
        raise NotAuthenticatedException()

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise NotAuthenticatedException()
    
    return user

# --- ПЕРЕВІРКА РОЛЕЙ ---
class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            # 403 Forbidden (це означає "залогінений, але не можна")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Operation not permitted. Required roles: {self.allowed_roles}"
            )
        return user

# Готові перевірки
allow_any_staff = RoleChecker(["worker", "manager", "analyst"])
allow_manager_only = RoleChecker(["manager"])
allow_analyst_access = RoleChecker(["analyst", "manager"])
# allow_admin_only = RoleChecker(["admin"])