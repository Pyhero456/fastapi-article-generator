from fastapi import FastAPI
from app.routes.responses import router, router_1,router_2,router_3
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.timing import timing_middleware
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models import User, RefreshToken
from app.auth import(hash_password, verify_password, create_access_token, create_refresh_token, limiter, get_current_user, hash_refresh_token)
from datetime import timedelta
from fastapi import HTTPException, status, Depends
from app.schemas import UserCreate, UserResponse, Token, RefreshRequest
from fastapi.security import OAuth2PasswordRequestForm
import logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path="crew/.env")


app = FastAPI(
    title="AI Article Generator",
    description="An AI Article Generating app"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.middleware("http")(timing_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_credentials= True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"]
)

@app.get("/")
def menu():
    return {"header":"AI Article Generator"}

Base.metadata.create_all(bind= engine)


@app.post("/register", response_model= UserResponse)
@limiter.limit("10/minute")
def register(request:Request,user:UserCreate, db:Session=Depends(get_db)):
    existing_user = (db.query(User).filter(User.username == user.username).first())

    if existing_user:
        logger.warning(f"Failed registration attempt for {user.username}")
        raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST, detail = "Username already exists")
    new_user = User(username = user.username, hashed_password = hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"User {new_user.username} registered")
    return new_user

@app.post("/login", response_model = Token)
@limiter.limit("5/minute")
def login(request:Request,user:OAuth2PasswordRequestForm = Depends(), db:Session = Depends(get_db)):
    db_user = (db.query(User).filter(User.username == user.username).first())
    if not db_user:
        logger.warning(f"Failed login attempt for {user.username}")
        raise HTTPException(status_code= status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not verify_password(user.password,db_user.hashed_password):
        logger.warning(f"Failed login attempt for {user.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail = "invalid username or password")

    access_token = create_access_token(username = db_user.username, expires_delta = timedelta(minutes=30))
    refresh_token, expires_at = create_refresh_token()

    db_refresh_token = RefreshToken(
        token_hash = hash_refresh_token(refresh_token),
        user_id = db_user.id,
        expires_at = expires_at
    )
    db.add(db_refresh_token)
    db.commit()
    logger.info(f"User {db_user.username} logged in")
    return {
        "access_token": access_token,
        "refresh_token":refresh_token,
        "token_type":"bearer"
    }

@app.post("/refresh", response_model=Token)
def refresh_token(data: RefreshRequest, db:Session = Depends(get_db)):
    token_hash = hash_refresh_token(data.refresh_token)
    stored_token = (db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first())

    if stored_token is None:
        raise HTTPException(status_code= status.HTTP_401_UNAUTHORIZED, detail = "Invalid refresh token")
    if stored_token.revoked:
        raise HTTPException(status_code= status.HTTP_401_UNAUTHORIZED, detail = "Refresh token has been revoked")
    if stored_token.expires_at <= datetime.utcnow():
        raise HTTPException(status_code= status.HTTP_401_UNAUTHORIZED, detail = "Refresh token has expired")

    user = stored_token.user
    stored_token.revoked = True

    new_access_token = create_access_token(
        username = user.username,
        expires_delta=timedelta(minutes=30)
    )
    new_refresh_token, expires_at = create_refresh_token()
    new_db_token= RefreshToken(
            token_hash = hash_refresh_token(new_refresh_token),
            user_id = user.id,
            expires_at = expires_at)
    db.add(new_db_token)
    db.commit()

    return {
        "access_token":new_access_token,
        "refresh_token":new_refresh_token,
        "token_type":"bearer"
    }


@app.post("/logout")
def logout(data:RefreshRequest, db:Session = Depends(get_db)):
    token_hash = hash_refresh_token(data.refresh_token)
    stored_token = (db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first())
    if stored_token:
        stored_token.revoked = True
        db.commit()
    return{
        "message":"Logged out successfully"
    }


@app.get("/me")
def get_me(current_user = Depends(get_current_user), db:Session = Depends(get_db)):
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .first()
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "api_access": current_user.api_access,
        "subscription_active": (
            subscription is not None
            and subscription.status == "active"
            and subscription.expires_at > datetime.utcnow()
        )
    }

def require_api_access(current_user:User = Depends(get_current_user)):
    if not current_user.api_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail = "API acess requires payment")
    return current_user


        
app.include_router(router_1)
app.include_router(router, dependencies=[Depends(require_api_access)])
app.include_router(router_3, dependencies=[Depends(require_api_access)])
app.include_router(router_2)

@app.post("/setup-admin")
def setup_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    admin_username = os.getenv("ADMIN_USERNAME")

    if not admin_username:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_USERNAME is not configured"
        )

    if current_user.username != admin_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    current_user.is_admin = True
    db.commit()
    db.refresh(current_user)

    return {"message": "Admin access granted"}
