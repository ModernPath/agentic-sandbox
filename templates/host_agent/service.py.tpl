"""Use cases for $Title. The API, the model tools, and the CLI all call these functions.

Business rules live here and only here. Raise ValueError (bad input) or LookupError (missing item)
with a message that is safe to show.
"""

from __future__ import annotations

STATUSES = ("open", "done")


def create_item(store, title: str, body: str = "") -> dict:
    title = (title or "").strip()
    if not 1 <= len(title) <= 200:
        raise ValueError("Title must be 1-200 characters")
    if len(body or "") > 5000:
        raise ValueError("Body must be at most 5000 characters")
    return store.create(title, body or "")


def list_items(store) -> list[dict]:
    return store.list()


def get_item(store, item_id: str):
    item = store.get(item_id)
    if item is None:
        raise LookupError("Item not found")
    return item


def set_status(store, item_id: str, status: str) -> bool:
    if status not in STATUSES:
        raise ValueError("Status must be open or done")
    if not store.set_status(item_id, status):
        raise LookupError("Item not found")
    return True
