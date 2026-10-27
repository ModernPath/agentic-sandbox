"""Request models for meeting prep. Shapes and bounds live here; the rules live in service.py."""

from pydantic import BaseModel, Field


class Attendee(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)


class BriefCreate(BaseModel):
    company: str = Field(min_length=2, max_length=120)
    website: str = Field(default="", max_length=500)
    meeting_date: str = Field(default="", max_length=10)
    purpose: str = Field(default="", max_length=500)
    attendees: list[Attendee] = Field(default_factory=list, max_length=10)
    notes_file_id: str = Field(default="", max_length=64)
