from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Role = Literal["user", "manager", "admin"]


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z][a-z0-9_.-]*$")
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identity(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = Field(default=False, strict=True)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserResponse


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserPage(BaseModel):
    items: list[UserResponse]
    total: int
    offset: int
    limit: int


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "manager"] | None = None
    is_active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def has_change(self):
        if self.role is None and self.is_active is None:
            raise ValueError("Provide role or is_active")
        return self
