from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.camera.types import NETWORK_TYPES, SourceType
from app.core.ppe import sanitize_enabled_classes

ConnectionStatus = Literal["starting", "running", "retrying", "stopped", "completed", "error"]


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    source_type: SourceType = Field(validation_alias=AliasChoices("source_type", "type"))
    source_uri: str | None = Field(default=None, min_length=1, max_length=500)
    device_index: int | None = Field(default=None, ge=0, le=15, strict=True)
    port: int | None = Field(default=None, ge=1, le=65535)
    source_username: str | None = Field(
        default=None, max_length=128, json_schema_extra={"writeOnly": True}
    )
    source_password: SecretStr | None = Field(default=None, max_length=128)
    clear_credentials: bool = False
    auth_mode: Literal["basic", "digest"] = "basic"
    onvif_device_uri: str | None = Field(default=None, max_length=500)
    site_id: int | None = Field(default=None, gt=0)
    enabled_classes: list[str] | None = None

    @field_validator("enabled_classes")
    @classmethod
    def validate_enabled(cls, value):
        return sanitize_enabled_classes(value)

    @model_validator(mode="after")
    def validate_source_fields(self):
        if self.source_type == "usb":
            if self.device_index is None or self.source_uri is not None:
                raise ValueError("USB requires device_index and does not accept source_uri")
        elif self.source_uri is None or self.device_index is not None:
            raise ValueError(
                "This source type requires source_uri and does not accept device_index"
            )
        if self.source_type not in NETWORK_TYPES and (
            self.port is not None
            or self.source_username is not None
            or self.source_password is not None
            or self.clear_credentials
            or self.auth_mode != "basic"
            or self.onvif_device_uri
        ):
            raise ValueError("Network/authentication fields are not valid for file/USB sources")
        return self


class CameraUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(None, min_length=1, max_length=100)
    source_type: SourceType | None = Field(
        default=None, validation_alias=AliasChoices("source_type", "type")
    )
    source_uri: str | None = Field(None, min_length=1, max_length=500)
    device_index: int | None = Field(default=None, ge=0, le=15, strict=True)
    port: int | None = Field(default=None, ge=1, le=65535)
    source_username: str | None = Field(
        default=None, max_length=128, json_schema_extra={"writeOnly": True}
    )
    source_password: SecretStr | None = Field(default=None, max_length=128)
    clear_credentials: bool = False
    auth_mode: Literal["basic", "digest"] | None = None
    onvif_device_uri: str | None = Field(default=None, max_length=500)
    site_id: int | None = Field(default=None, gt=0)
    enabled_classes: list[str] | None = None

    @field_validator("enabled_classes")
    @classmethod
    def validate_enabled(cls, value):
        return sanitize_enabled_classes(value)


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    source_type: SourceType
    source_uri: str
    device_index: int | None = None
    port: int | None = None
    auth_mode: Literal["basic", "digest"] = "basic"
    onvif_device_uri: str | None = None
    site_id: int | None
    enabled_classes: list[str]
    is_active: bool
    created_at: datetime
    is_running: bool = False
    connection_status: ConnectionStatus = "stopped"
    last_error: str | None = None
