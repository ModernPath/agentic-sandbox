"""Output schemas for Exa Agent runs. Bounded, and without contact fields (see technical spec F2)."""

import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

PEOPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "maxItems": 25,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "job_title": {"type": "string"},
                    "company": {"type": "string"},
                    "profile_url": {"type": "string", "format": "uri"},
                },
                "required": ["name", "job_title", "company"],
            },
        }
    },
    "required": ["people"],
}

COMPANY_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "maxItems": 25,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string", "format": "uri"},
                    "industry": {"type": "string"},
                    "headquarters": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "website"],
            },
        }
    },
    "required": ["companies"],
}


def clean_text(value) -> str:
    """Remove control characters (including newlines and escape codes) before printing model or web text."""
    return _CONTROL.sub("", str(value or ""))
