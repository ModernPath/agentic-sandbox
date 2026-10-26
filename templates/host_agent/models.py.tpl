"""Request models for $Title. Validation lives here; the API maps errors to HTTP codes."""

from typing import Literal

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=5000)


class ItemUpdate(BaseModel):
    status: Literal["open", "done"]
