"""Model-callable tools for meeting prep. Each tool calls one service function.

Parameter types come from the signatures and descriptions from the docstrings (tool_from_function).
Errors are returned as data ({"error": ...}), never raised into the model loop. There is no delete tool:
deleting a brief is a person's action on the page.
"""

from __future__ import annotations

from typing import Callable, Optional

from sandbox_blocks.tools import Tool, tool_from_function

from . import service


def build_tools(store, *, search, read_page, llm, signals, notes,
                on_call: Optional[Callable[[str], None]] = None) -> list[Tool]:
    def prepare_meeting(company: str, website: str = "", meeting_date: str = "", purpose: str = "",
                        attendees: str = "", notes_file_id: str = "") -> dict:
        """Prepare a one-page brief before a meeting with a company: recent public news with citations, sales radar signals that mention it, notes from an uploaded file, talking points, and open questions. Takes up to a minute.

        Args:
            company: The company's name.
            website: The company's website, http(s), if known.
            meeting_date: The meeting date as YYYY-MM-DD, if known.
            purpose: What the meeting is for, in a sentence.
            attendees: People attending, as "Name (Role); Name (Role)".
            notes_file_id: The id of an uploaded notes file, if the user attached one.
        """
        request = {"company": company, "website": website, "meeting_date": meeting_date, "purpose": purpose,
                   "attendees": attendees, "notes_file_id": notes_file_id}
        return _safe(lambda: service.prepare_brief(store, request, search=search, read_page=read_page, llm=llm,
                                                   signals=signals, notes=notes))

    def list_briefs() -> dict:
        """List meeting briefs, newest first."""
        return _safe(lambda: {"briefs": service.list_briefs(store)})

    def get_brief(brief_id: str) -> dict:
        """Get one meeting brief by its exact id, with its sources and radar signals."""
        return _safe(lambda: service.get_brief(store, brief_id))

    functions = [prepare_meeting, list_briefs, get_brief]
    return [tool_from_function(fn, on_call=on_call) for fn in functions]


def _safe(call):
    try:
        return call()
    except (ValueError, LookupError) as error:
        return {"error": str(error)}
    except Exception:  # keep provider and storage details out of the model loop
        return {"error": "Meeting prep failed. Try again later."}
