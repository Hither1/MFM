"""Execution of the public tools against the controller (upstream `dispatcher.py`).

The checkpoint gate is the one piece of policy here: while a checkpoint is requested
and not yet saved, every tool but `save_compact_checkpoint` is refused with the
sentence that tells the model what to do; while a recovery is being delivered, every
tool is. The notes files are the agent's own and never go through the controller.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mfm.vista.controller import atomic_write_text
from mfm.vista.tools import MAX_GUIDE_CHARS, MAX_WORKING_CHARS


@dataclass
class ToolExecution:
    text: str
    success: bool
    images: tuple[dict[str, Any], ...] = ()
    #: End the model's turn right after the response (a checkpoint handoff).
    interrupt_after: bool = False
    boundary_reason: str | None = None


class GameToolDispatcher:
    def __init__(self, *, controller: Any, guide_path: Path, working_path: Path) -> None:
        self.controller = controller
        self.guide_path = Path(guide_path)
        self.working_path = Path(working_path)
        self.calls: dict[str, int] = {}

    def execute(self, tool: str, arguments: Any, call_id: str) -> ToolExecution:
        self.calls[tool] = self.calls.get(tool, 0) + 1
        if self.controller.compact_restore_marker.exists():
            return ToolExecution("Compact recovery is being delivered.", False)
        if self.controller.compact_checkpoint_marker.exists() and tool != "save_compact_checkpoint":
            return ToolExecution("Save the compact checkpoint before using another tool.", False)
        if not isinstance(arguments, dict):
            arguments = {}
        if tool == "read_guide":
            return self._read(self.guide_path, arguments, "GUIDE.md")
        if tool == "read_working":
            return self._read(self.working_path, arguments, "WORKING.md")
        if tool == "write_guide":
            return self._write(self.guide_path, arguments, "GUIDE.md", MAX_GUIDE_CHARS)
        if tool == "write_working":
            out = self._write(self.working_path, arguments, "WORKING.md", MAX_WORKING_CHARS)
            if out.success:
                self.controller.record_working_write()
            return out
        if tool in {"save_compact_checkpoint", "inspect", "read_pixels", "history", "play"}:
            response = self.controller.handle({"method": tool, "request_id": call_id,
                                               "arguments": arguments})
            return execution_from_response(response)
        return ToolExecution("Unknown tool.", False)

    @staticmethod
    def _read(path: Path, arguments: dict[str, Any], name: str) -> ToolExecution:
        if arguments:
            return ToolExecution("Invalid arguments.", False)
        try:
            return ToolExecution(path.read_text(encoding="utf-8", errors="replace"), True)
        except FileNotFoundError:
            return ToolExecution(f"{name} does not exist.", True)
        except OSError:
            return ToolExecution(f"{name} is unavailable.", False)

    @staticmethod
    def _write(path: Path, arguments: dict[str, Any], name: str, cap: int) -> ToolExecution:
        content = arguments.get("content")
        if (set(arguments) != {"content"} or not isinstance(content, str)
                or not content.strip() or len(content) > cap):
            return ToolExecution(f"Invalid {name} content.", False)
        try:
            atomic_write_text(path, content.strip() + "\n")
        except OSError:
            return ToolExecution(f"{name} could not be updated.", False)
        return ToolExecution(f"{name} updated.", True)


def execution_from_response(response: dict[str, Any]) -> ToolExecution:
    metadata = response.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {"error": "Controller returned no metadata."}
    images: list[dict[str, Any]] = []
    image = response.get("image")
    if isinstance(image, dict) and isinstance(image.get("data"), str):
        images.append({**image, "steer_text": visual_result_label(metadata)})
    views = metadata.get("views")
    if isinstance(response.get("images"), list) and isinstance(views, list):
        if len(response["images"]) != len(views):
            return _image_error("Controller returned mismatched inspection views.")
        for index, (view, view_image) in enumerate(zip(views, response["images"]), start=1):
            if not isinstance(view, dict) or not isinstance(view_image, dict) \
                    or not isinstance(view_image.get("data"), str):
                return _image_error("Controller returned an invalid inspection view.")
            label = visual_result_label({"visual_kind": "inspection", "current_state_unchanged": True,
                                         "view_count": len(views), "index": index, **view})
            images.append({**view_image, "steer_text": label})
    return ToolExecution(json.dumps(metadata, separators=(",", ":"), default=str),
                         response.get("ok") is True, tuple(images))


def visual_result_label(metadata: dict[str, Any]) -> str:
    if metadata.get("visual_kind") == "inspection":
        attributes = ""
        if type(metadata.get("index")) is int:
            attributes += f' index="{metadata["index"]}"'
        if type(metadata.get("view_count")) is int:
            attributes += f' count="{metadata["view_count"]}"'
        attributes += f' turn="{metadata.get("turn")}" frame="{metadata.get("frame")}"'
        region = metadata.get("region")
        if isinstance(region, dict):
            attributes += (f' region="{region.get("x")},{region.get("y")},'
                           f'{region.get("width")},{region.get("height")}"')
        size = metadata.get("image_size")
        if isinstance(size, dict) and type(size.get("width")) is int and type(size.get("height")) is int:
            attributes += f' size="{size["width"]}x{size["height"]}"'
        return f"<inspection_visual{attributes}></inspection_visual>"
    visual = metadata.get("visual") if isinstance(metadata.get("visual"), dict) else {}
    turn = visual.get("turn", metadata.get("turn"))
    attributes = ""
    if type(visual.get("width")) is int and type(visual.get("height")) is int:
        attributes += f' size="{visual["width"]}x{visual["height"]}"'
    if metadata.get("recovery_observation") is True:
        meaning = "Current state restored after context recovery."
    elif metadata.get("action_applied") is True:
        meaning = "Current state after the action."
    else:
        meaning = "Current state."
    return (f'<current_visual turn="{turn}" frame="{visual.get("final_frame")}" '
            f'frame_count="{visual.get("frame_count")}"{attributes}>{meaning}</current_visual>')


def _image_error(message: str) -> ToolExecution:
    return ToolExecution(json.dumps({"error": message}, separators=(",", ":")), False)
