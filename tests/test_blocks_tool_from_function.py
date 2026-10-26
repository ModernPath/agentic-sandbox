import pytest

from sandbox_blocks.tools import ToolCall, tool_from_function


def add_item(title: str, url: str, note: str = "", tags: str = "", priority: int = 0, unread: bool = False):
    """Save a reading-list item.

    Args:
      title: Title of the item.
      url: http(s) URL.
      note: Optional note.
      tags: Optional comma-separated tags.
      priority: Higher means sooner.
      unread: Only unread items.
    """
    return {"title": title, "url": url, "note": note, "tags": tags, "priority": priority, "unread": unread}


def test_schema_comes_from_type_hints_defaults_and_docstring():  # H-1
    tool = tool_from_function(add_item)
    assert tool.name == "add_item"
    assert tool.description == "Save a reading-list item."
    assert tool.parameters["type"] == "object"
    props = tool.parameters["properties"]
    assert props["title"] == {"type": "string", "description": "Title of the item."}
    assert props["priority"]["type"] == "integer" and props["unread"]["type"] == "boolean"
    assert tool.parameters["required"] == ["title", "url"]


def test_handler_calls_the_function_with_arguments():  # H-2
    tool = tool_from_function(add_item)
    assert tool.handler({"title": "T", "url": "https://x.example", "priority": 2})["priority"] == 2


def test_on_call_hook_records_each_invocation():  # H-3
    seen = []
    tool = tool_from_function(add_item, on_call=seen.append)
    tool.handler({"title": "T", "url": "https://x.example"})
    assert seen == ["add_item"]


def test_function_without_docstring_still_gets_a_schema():  # H-4
    def ping(target: str):
        return {"target": target}
    tool = tool_from_function(ping)
    assert tool.description == "" and tool.parameters["required"] == ["target"]


def test_name_and_description_can_be_overridden():  # H-5
    tool = tool_from_function(add_item, name="save_item", description="Save it.")
    assert tool.name == "save_item" and tool.description == "Save it."


def test_unsupported_annotation_is_rejected_at_definition():  # H-6
    def bad(items: list):
        return items
    with pytest.raises(TypeError, match="items"):
        tool_from_function(bad)
