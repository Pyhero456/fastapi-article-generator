import os
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from datetime import timedelta
from fastapi import HTTPException, status, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
import hashlib
import secrets


load_dotenv(dotenv_path="crew/.env")

limiter = Limiter(key_func=get_remote_address)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")

def hash_password(password:str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password:str, hashed_password:str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(
        username:str,
        expires_delta:timedelta|None = None
):
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    payload = {
        "sub" : username,
        "exp" : expire
    }
    return jwt.encode(payload,SECRET_KEY,algorithm=ALGORITHM)

def decode_access_token(token:str):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username is None:
            return None
        
        return username

    except jwt.InvalidTokenError:
        return None

def get_current_user(token:str = Depends(oauth2_scheme), db:Session=Depends(get_db)):
    username = decode_access_token(token)

    if username is None:
        raise HTTPException(
            status_code= status.HTTP_401_UNAUTHORIZED, detail = "Invalid or expired token")
    user = (db.query(User).filter(User.username == username).first())
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail = "User not found")
    return user


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)

def hash_refresh_token(token:str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def create_refresh_token():
    token = generate_refresh_token()

    expires_at = (datetime.utcnow() + timedelta(days=7))

    return token,expires_at

def generate_payment_reference():
    return f"API - {secrets.token_hex(4).upper()}"

