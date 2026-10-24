from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.password_policy import validate_password

UserRole = Literal["admin", "supervisor", "viewer"]


class LoginResponse(BaseModel):
    authenticated: bool = True
    must_change_password: bool


class MeResponse(BaseModel):
    id: int
    username: str
    role: UserRole
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
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    # Provisioning additional administrators is reserved for the local CLI.
    role: Literal["supervisor", "viewer"] = "viewer"


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["supervisor", "viewer"] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime


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
