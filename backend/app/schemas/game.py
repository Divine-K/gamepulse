import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GameCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    genre: str | None = Field(default=None, max_length=50)


class GameUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    genre: str | None = Field(default=None, max_length=50)


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str
    genre: str | None
    created_at: datetime
    updated_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(default="Default", min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    """Key metadata. The secret is never included after creation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="Full API key. Shown only once; store it securely.")
