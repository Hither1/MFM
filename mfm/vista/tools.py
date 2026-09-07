"""The public tool contracts of the VISTA player, with the game made a parameter.

Upstream (`vista_arc3/codex/tools.py`) hard-codes the ARC action vocabulary in `play`
and a square display in `inspect` / `read_pixels`. Here the benchmark supplies the
`play` input schema and description, and the visual tools take the frame's own width
and height: a region is addressed in the frame's pixels, and a crop is magnified to fit
within the frame's own size. Everything else -- the notes tools, `history`, the
checkpoint tool, the caps -- is the upstream contract verbatim.
"""
from __future__ import annotations

from typing import Any

MAX_GUIDE_CHARS = 64 * 1024
MAX_WORKING_CHARS = 16 * 1024
MAX_INSPECTION_VIEWS = 16
MAX_INSPECTION_QUESTION_CHARS = 1024
MAX_INSPECTION_LABEL_CHARS = 128
MAX_PIXEL_READOUT_VIEWS = 64
MAX_PIXEL_READOUT_SAMPLES = 4096

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False}
_WRITES = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
           "openWorldHint": False}


def build_play_tool(input_schema: dict[str, Any], description: str) -> dict[str, Any]:
    """`play`: the benchmark's one-action schema and its own description of it."""
    if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
        raise ValueError("the play schema must be a JSON object schema")
    return {
        "name": "play",
        "description": description,
        "inputSchema": input_schema,
        "annotations": {"readOnlyHint": False, "destructiveHint": False,
                        "idempotentHint": False, "openWorldHint": False},
    }


READ_GUIDE_TOOL = {
    "name": "read_guide",
    "description": "Read `GUIDE.md`.",
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
    "annotations": dict(_READ_ONLY),
}

HISTORY_TOOL = {
    "name": "history",
    "description": (
        "Read the objective action and environment-result records of this episode "
        "without changing anything. `events` returns exact public action/result records "
        "by turn; use start_turn, end_turn, and limit to select a range (the most recent "
        "records when no range is given)."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["view"],
        "properties": {
            "view": {"type": "string", "enum": ["events"]},
            "start_turn": {"type": "integer", "minimum": 0, "maximum": 999999},
            "end_turn": {"type": "integer", "minimum": 0, "maximum": 999999},
            "limit": {"type": "integer", "minimum": 1, "maximum": 128, "default": 64},
        },
    },
    "annotations": dict(_READ_ONLY),
}

READ_WORKING_TOOL = {
    "name": "read_working",
    "description": "Read the agent-authored temporary state for the current episode.",
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
    "annotations": dict(_READ_ONLY),
}

WRITE_WORKING_TOOL = {
    "name": "write_working",
    "description": (
        "Replace the agent-authored temporary state for the current episode. It "
        "persists across context handoffs."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["content"],
        "properties": {"content": {"type": "string", "minLength": 1,
                                   "maxLength": MAX_WORKING_CHARS}},
    },
    "annotations": dict(_WRITES),
}

WRITE_GUIDE_TOOL = {
    "name": "write_guide",
    "description": "Write the complete contents of `GUIDE.md`, replacing its previous contents.",
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["content"],
        "properties": {"content": {"type": "string", "minLength": 1,
                                   "maxLength": MAX_GUIDE_CHARS}},
    },
    "annotations": dict(_WRITES),
}

SAVE_COMPACT_CHECKPOINT_TOOL = {
    "name": "save_compact_checkpoint",
    "description": (
        "Atomically save the pre-compaction checkpoint. Set guide to a complete "
        "replacement GUIDE.md only when the durable model materially changed; "
        "otherwise set it to null. Store in working_memory only the current "
        "continuation state that cannot be recovered from GUIDE.md and the current "
        "visual: the active plan, its next visible prediction, unresolved "
        "contradictions, and any necessary turn/frame references."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["guide", "working_memory"],
        "properties": {
            "guide": {"type": ["string", "null"], "minLength": 1, "maxLength": MAX_GUIDE_CHARS},
            "working_memory": {"type": "string", "minLength": 1, "maxLength": MAX_WORKING_CHARS},
        },
    },
    "annotations": dict(_WRITES),
}


def _check_size(width: int, height: int) -> None:
    for name, v in (("width", width), ("height", height)):
        if type(v) is not int or v < 1:
            raise ValueError(f"{name} must be a positive integer")


def region_schema(width: int, height: int) -> dict[str, Any]:
    _check_size(width, height)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["x", "y", "width", "height"],
        "properties": {
            "x": {"type": "integer", "minimum": 0, "maximum": width - 1},
            "y": {"type": "integer", "minimum": 0, "maximum": height - 1},
            "width": {"type": "integer", "minimum": 1, "maximum": width},
            "height": {"type": "integer", "minimum": 1, "maximum": height},
        },
    }


def build_inspect_tool(width: int, height: int) -> dict[str, Any]:
    _check_size(width, height)
    view_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["label", "turn"],
        "properties": {
            "label": {"type": "string", "minLength": 1, "maxLength": MAX_INSPECTION_LABEL_CHARS},
            "turn": {"type": "integer", "minimum": 0, "maximum": 999999},
            "frame": {"type": "integer", "minimum": 0, "maximum": 999999,
                      "description": "Exact archived frame; omit for the final frame."},
            "region": region_schema(width, height),
        },
    }
    return {
        "name": "inspect",
        "description": (
            "Inspect one or more archived visuals without changing the current state. "
            "Each view selects an archived turn; omit frame to use that turn's final "
            "frame (turn 0 is the initial view; a turn's frames are the views recorded "
            "while its action ran, the last one being the view its result carried). "
            "Omit region to see the full visual, or select a rectangular region in the "
            f"visual's own {width}x{height} pixel coordinates (x right, y down). A "
            "selected region is cropped exactly from that visual and enlarged "
            f"proportionally to fit within {width}x{height} without smoothing. State "
            "the visual question these views should answer and give each view a short "
            "label. Include the evidence needed to answer that question in the same "
            "request. The selected views are returned in request order; your question "
            "and labels remain in the inspect call."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["question", "views"],
            "properties": {
                "question": {"type": "string", "minLength": 1,
                             "maxLength": MAX_INSPECTION_QUESTION_CHARS},
                "views": {"type": "array", "minItems": 1, "maxItems": MAX_INSPECTION_VIEWS,
                          "items": view_schema},
            },
        },
        "annotations": dict(_READ_ONLY),
    }


def build_read_pixels_tool(width: int, height: int) -> dict[str, Any]:
    _check_size(width, height)
    view_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["label", "turn", "region", "rows", "columns"],
        "properties": {
            "label": {"type": "string", "minLength": 1, "maxLength": MAX_INSPECTION_LABEL_CHARS},
            "turn": {"type": "integer", "minimum": 0, "maximum": 999999},
            "frame": {"type": "integer", "minimum": 0, "maximum": 999999,
                      "description": "Exact archived frame; omit for the final frame."},
            "region": region_schema(width, height),
            "rows": {"type": "integer", "minimum": 1, "maximum": height},
            "columns": {"type": "integer", "minimum": 1, "maximum": width},
        },
    }
    return {
        "name": "read_pixels",
        "description": (
            "Read exact discrete color samples from one or more archived visuals "
            "without changing the current state. Each view divides its selected "
            "rectangular region into equal rows and columns and samples the center "
            "pixel of every part from the archived PNG. The result contains one RGB "
            "symbol palette and one compact row string per sampled row for each view "
            f"in request order. At most {MAX_PIXEL_READOUT_VIEWS} views may be "
            f"selected, with at most {MAX_PIXEL_READOUT_SAMPLES} samples total per "
            "call. This tool only measures pixels; it does not align, transform, "
            "compare, or interpret them. State the visual question and give each view "
            "a short label; those remain in this call."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["question", "views"],
            "properties": {
                "question": {"type": "string", "minLength": 1,
                             "maxLength": MAX_INSPECTION_QUESTION_CHARS},
                "views": {"type": "array", "minItems": 1,
                          "maxItems": MAX_PIXEL_READOUT_VIEWS, "items": view_schema},
            },
        },
        "annotations": dict(_READ_ONLY),
    }


def build_tools(play_tool: dict[str, Any], width: int, height: int, *,
                include_compact_checkpoint: bool = True) -> tuple[dict[str, Any], ...]:
    tools = (
        play_tool,
        build_inspect_tool(width, height),
        build_read_pixels_tool(width, height),
        HISTORY_TOOL,
        READ_GUIDE_TOOL,
        WRITE_GUIDE_TOOL,
        READ_WORKING_TOOL,
        WRITE_WORKING_TOOL,
    )
    if include_compact_checkpoint:
        return (*tools, SAVE_COMPACT_CHECKPOINT_TOOL)
    return tools


TOOL_NAMES = ("play", "inspect", "read_pixels", "history", "read_guide", "write_guide",
              "read_working", "write_working", "save_compact_checkpoint")
