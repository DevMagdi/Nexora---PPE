from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.password_policy import validate_password


class LoginResponse(BaseModel):
    authenticated: bool = True
    must_change_password: bool


class MeResponse(BaseModel):
    id: int
    username: str
    sector: str
    role: str
    must_change_password: bool


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password(value)
        return value


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    sector: Literal["construction", "medical", "both"]
    # Site administrators may issue viewer/operator accounts. Admin accounts are
    # deliberately reserved for the on-prem operator/CLI bootstrap process.
    role: Literal["operator", "viewer"] = "viewer"


class UserUpdateRequest(BaseModel):
    sector: Literal["construction", "medical", "both"] | None = None
    role: Literal["operator", "viewer"] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    sector: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserIssuedResponse(UserResponse):
    initial_password: str


class AuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    target_type: str | None
    target_id: str | None
    ip_hash: str | None
    details: dict
    created_at: datetime
