from datetime import datetime, timedelta
from typing import Any, Optional, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.users import User as UserModel
from utils.database import get_db

# ------------------------------------------------------------------------------
# Configuration (use env vars in real systems)
# ------------------------------------------------------------------------------
SECRET_KEY = "123-next"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


# ------------------------------------------------------------------------------
# Password Utilities
# ------------------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    return cast(str, pwd_context.hash(password))


# ------------------------------------------------------------------------------
# User Utilities
# ------------------------------------------------------------------------------
def get_user(db: Session, username: str) -> Optional[UserModel]:
    return (
        db.query(UserModel)
        .filter(UserModel.username == username)
        .first()
    )


def authenticate_user(db: Session, username: str, password: str) -> Optional[UserModel]:
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


# ------------------------------------------------------------------------------
# JWT Utilities
# ------------------------------------------------------------------------------
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return cast(str, jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM))


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(db, token_data.username if token_data.username else "")
    if user is None:
        raise credentials_exception
    return User(username=user.username)


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    # if current_user.disabled:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
