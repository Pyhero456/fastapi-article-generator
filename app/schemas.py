from typing import Optional 
from pydantic import BaseModel, Field
from enum import Enum

class PaymentStatus(Enum):
    pending = "pending"
    paid = "paid"
    rejected = "rejected"

class Plan(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    UNLIMITED = "unlimited"

class ArticleCreate(BaseModel):
    topic: str = Field(min_length = 1, max_length = 100)

class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(max_length=100, default=None)

class ArticleOut(BaseModel):
    title:str = Field(description = "Header of the article")
    content:str = Field(description= "Content of the Article")
    sources:str = Field(description= "The links of websites visited")
    word_count:int = Field(description = "Word count of the article")
    user_id:int = Field(description = "The current user's id")
    

class UserCreate(BaseModel):
    username:str
    password:str

class UserResponse(BaseModel):
    id:int
    username:str

class Token(BaseModel):
    access_token:str
    refresh_token:str
    token_type:str

class RefreshRequest(BaseModel):
    refresh_token:str

class SubscriptionRequest(BaseModel):
    plan: Plan

class PaymentReferenceResponse(BaseModel):
    reference:str
    amount_cents:int
    status:str
