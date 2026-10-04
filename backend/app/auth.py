from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_EXPIRE_MINUTES
from .database import get_db
from .models import User

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                          headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError):
        raise error
    user = db.get(User, user_id)
    if user is None:
        raise error
    return user
