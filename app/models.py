from typing import Literal

from pydantic import BaseModel, Field


RoleName = Literal["admin", "user", "guest"]


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, examples=["alice"])


class User(UserBase):
    password: str = Field(..., min_length=1, examples=["qwerty123"])


class UserCreate(User):
    role: RoleName = Field(default="user", examples=["user"])


class UserInDB(UserBase):
    hashed_password: str
    role: RoleName = "user"


class LoginRequest(User):
    pass


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Message(BaseModel):
    message: str


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, examples=["Buy groceries"])
    description: str = Field(..., min_length=1, examples=["Milk, eggs, bread"])


class TodoUpdate(TodoCreate):
    completed: bool = Field(..., examples=[True])


class Todo(TodoUpdate):
    id: int
