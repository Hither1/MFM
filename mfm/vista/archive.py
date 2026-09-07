"""The lossless visual memory: every frame on disk, addressed by turn and frame.

    frames/turn_000012_frame_003.png

Turn 0 holds the initial view. Turn k's frames are the views recorded while play k's
action ran (the benchmark decides how often: every tick on ARC, every N ticks on MCU
where one action is tens of ticks, one per batch on KiCad), the last of them being the
view play k's result carried. `inspect` and `read_pixels` are the two readers, ported
from the upstream controller with the square display replaced by the frame's own size:
a region is addressed in the frame's pixels and a crop is enlarged proportionally to fit
within the frame's own width and height, nearest-neighbour (no smoothing -- the point is
to read pixels that were there, not to invent ones that were not).
"""
from __future__ import annotations

import base64
import io
import string
from pathlib import Path
from typing import Any

from PIL import Image

from mfm.vista.tools import (MAX_INSPECTION_LABEL_CHARS, MAX_INSPECTION_QUESTION_CHARS,
                             MAX_INSPECTION_VIEWS, MAX_PIXEL_READOUT_SAMPLES,
                             MAX_PIXEL_READOUT_VIEWS)

#: Upstream's symbol alphabet for pixel readouts: one symbol per distinct colour seen in
#: the episode, in order of first appearance, stable for the rest of the run.
PIXEL_READOUT_SYMBOLS = string.ascii_letters + string.digits + "!#$%&*+-=?@^_~"


class FrameArchive:
    def __init__(self, frames_dir: Path, width: int | None = None,
                 height: int | None = None) -> None:
        self.dir = Path(frames_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.frames_written = 0
        self.bytes_written = 0
        self._next: dict[int, int] = {}
        self._symbol_by_color: dict[tuple[int, int, int], str] = {}
        for p in self.dir.glob("turn_*_frame_*.png"):
            turn = self._turn_number(p)
            self._next[turn] = max(self._next.get(turn, 0), self._frame_number(p) + 1)

    # -- writing --------------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        if self.width is None or self.height is None:
            raise RuntimeError("the archive has no frame yet")
        return self.width, self.height

    def add(self, turn: int, png: bytes) -> int:
        """Archive one frame under `turn`; returns its frame index within the turn.

        The first frame fixes the archive's size; a later frame of another size is
        refused rather than resized, because `inspect` promises exact pixels."""
        with Image.open(io.BytesIO(png)) as im:
            size = im.size
        if self.width is None:
            self.width, self.height = size
        elif size != (self.width, self.height):
            raise ValueError(f"frame is {size[0]}x{size[1]}, the archive is "
                             f"{self.width}x{self.height}")
        index = self._next.get(turn, 0)
        path = self.dir / f"turn_{turn:06d}_frame_{index:03d}.png"
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(png)
        tmp.replace(path)
        self._next[turn] = index + 1
        self.frames_written += 1
        self.bytes_written += len(png)
        return index

    # -- addressing -------------------------------------------------------------------

    @staticmethod
    def _frame_number(path: Path) -> int:
        return int(path.stem.rsplit("_", 1)[-1])

    @staticmethod
    def _turn_number(path: Path) -> int:
        return int(path.stem.split("_")[1])

    def paths(self, turn: int) -> list[Path]:
        return sorted(self.dir.glob(f"turn_{turn:06d}_frame_*.png"), key=self._frame_number)

    def last(self, turn: int) -> Path | None:
        paths = self.paths(turn)
        return paths[-1] if paths else None

    def frame_count(self, turn: int) -> int:
        return self._next.get(turn, 0)

    def visual(self, turn: int) -> dict[str, Any] | None:
        """The `visual` block a play result carries: how to address this turn's frames."""
        paths = self.paths(turn)
        if not paths:
            return None
        return {"turn": turn, "frame_count": len(paths),
                "final_frame": self._frame_number(paths[-1]),
                "width": self.width, "height": self.height}

    def _select(self, selection: dict[str, Any], index: int) -> tuple[Path, list[Path]]:
        turn = selection.get("turn")
        frame = selection.get("frame")
        if type(turn) is not int or not 0 <= turn <= 999999:
            raise ValueError(f"View {index}: invalid turn.")
        if "frame" in selection and (type(frame) is not int or not 0 <= frame <= 999999):
            raise ValueError(f"View {index}: invalid frame.")
        paths = self.paths(turn)
        if not paths:
            raise ValueError(f"View {index}: no frames found for turn {turn}.")
        selected = paths[-1]
        if frame is not None:
            matching = [p for p in paths if self._frame_number(p) == frame]
            if not matching:
                raise ValueError(f"View {index}: no frame {frame} found for turn {turn}.")
            selected = matching[0]
        return selected, paths

    def region(self, value: object) -> tuple[int, int, int, int]:
        width, height = self.size
        if value is None:
            return 0, 0, width, height
        if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
            raise ValueError("Invalid region")
        x, y, w, h = (value.get(k) for k in ("x", "y", "width", "height"))
        if any(type(v) is not int for v in (x, y, w, h)):
            raise ValueError("Invalid region")
        assert isinstance(x, int) and isinstance(y, int) and isinstance(w, int) and isinstance(h, int)
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            raise ValueError("Invalid region")
        return x, y, w, h

    # -- inspect ----------------------------------------------------------------------

    @staticmethod
    def _check_request(arguments: object, max_views: int) -> list[dict[str, Any]]:
        if (not isinstance(arguments, dict) or set(arguments) != {"question", "views"}
                or not isinstance(arguments.get("question"), str)
                or not arguments["question"].strip()
                or len(arguments["question"]) > MAX_INSPECTION_QUESTION_CHARS
                or not isinstance(arguments.get("views"), list)
                or not 1 <= len(arguments["views"]) <= max_views):
            raise ValueError("Invalid arguments.")
        return arguments["views"]

    def inspect(self, arguments: object) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """(view metadata, images) for an `inspect` request; ValueError with the
        upstream wording on a bad request."""
        views = self._check_request(arguments, MAX_INSPECTION_VIEWS)
        metadata_views: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []
        for index, view in enumerate(views, start=1):
            metadata, image = self._inspection_view(view, index)
            metadata_views.append(metadata)
            images.append(image)
        return metadata_views, images

    def _inspection_view(self, selection: object, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
        if (not isinstance(selection, dict) or not isinstance(selection.get("label"), str)
                or not selection["label"].strip()
                or len(selection["label"]) > MAX_INSPECTION_LABEL_CHARS
                or "turn" not in selection
                or set(selection) - {"label", "turn", "frame", "region"}):
            raise ValueError(f"View {index}: invalid selection.")
        if "region" in selection and selection.get("region") is None:
            raise ValueError(f"View {index}: invalid region.")
        try:
            region = self.region(selection.get("region"))
        except ValueError as exc:
            raise ValueError(f"View {index}: invalid region.") from exc
        selected, paths = self._select(selection, index)
        width, height = self.size
        try:
            x, y, w, h = region
            with Image.open(selected) as archived:
                if archived.size != (width, height):
                    raise ValueError("Archived visual has an unexpected size")
                visual = archived.convert("RGB").crop((x, y, x + w, y + h))
            factor = min(width / w, height / h)
            rendered = (max(1, int(w * factor)), max(1, int(h * factor)))
            image = visual.resize(rendered, Image.Resampling.NEAREST) if rendered != visual.size else visual
            out = io.BytesIO()
            image.save(out, format="PNG")
        except (OSError, ValueError, IndexError, KeyError, TypeError) as exc:
            raise ValueError(f"View {index}: archived visual could not be rendered.") from exc
        metadata = {
            "index": index, "turn": selection["turn"], "frame": self._frame_number(selected),
            "available_frames": len(paths),
            "available_frame_range": [self._frame_number(paths[0]), self._frame_number(paths[-1])],
            "region": {"x": x, "y": y, "width": w, "height": h},
            "image_size": {"width": image.width, "height": image.height},
        }
        return metadata, {"mime_type": "image/png", "detail": "original",
                          "data": base64.b64encode(out.getvalue()).decode("ascii")}

    # -- read_pixels ------------------------------------------------------------------

    def read_pixels(self, arguments: object) -> dict[str, Any]:
        views = self._check_request(arguments, MAX_PIXEL_READOUT_VIEWS)
        sampled: list[tuple[dict[str, Any], list[list[tuple[int, int, int]]]]] = []
        total = 0
        for index, view in enumerate(views, start=1):
            metadata, samples = self._pixel_readout_view(view, index)
            total += metadata["rows"] * metadata["columns"]
            if total > MAX_PIXEL_READOUT_SAMPLES:
                raise ValueError(f"At most {MAX_PIXEL_READOUT_SAMPLES} samples may be requested.")
            sampled.append((metadata, samples))
        colors = {c for _, samples in sampled for row in samples for c in row}
        unseen = sorted(colors.difference(self._symbol_by_color))
        if len(self._symbol_by_color) + len(unseen) > len(PIXEL_READOUT_SYMBOLS):
            raise ValueError("The pixel readout color limit has been reached.")
        for color in unseen:
            self._symbol_by_color[color] = PIXEL_READOUT_SYMBOLS[len(self._symbol_by_color)]
        palette = {sym: f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                   for c, sym in self._symbol_by_color.items() if c in colors}
        metadata_views = []
        for metadata, samples in sampled:
            metadata["samples"] = ["".join(self._symbol_by_color[c] for c in row) for row in samples]
            metadata_views.append(metadata)
        return {"visual_kind": "pixel_readout", "current_state_unchanged": True,
                "sampling": "equal-bin-centers", "palette": palette, "sample_count": total,
                "view_count": len(metadata_views), "views": metadata_views}

    def _pixel_readout_view(self, selection: object, index: int
                            ) -> tuple[dict[str, Any], list[list[tuple[int, int, int]]]]:
        if (not isinstance(selection, dict) or not isinstance(selection.get("label"), str)
                or not selection["label"].strip()
                or len(selection["label"]) > MAX_INSPECTION_LABEL_CHARS
                or "turn" not in selection or "region" not in selection
                or set(selection) - {"label", "turn", "frame", "region", "rows", "columns"}):
            raise ValueError(f"View {index}: invalid selection.")
        width, height = self.size
        rows, columns = selection.get("rows"), selection.get("columns")
        if (type(rows) is not int or type(columns) is not int
                or not 1 <= rows <= height or not 1 <= columns <= width):
            raise ValueError(f"View {index}: invalid sample dimensions.")
        try:
            region = self.region(selection.get("region"))
        except ValueError as exc:
            raise ValueError(f"View {index}: invalid region.") from exc
        selected, paths = self._select(selection, index)
        try:
            x, y, w, h = region
            xs = [x + ((2 * c + 1) * w) // (2 * columns) for c in range(columns)]
            ys = [y + ((2 * r + 1) * h) // (2 * rows) for r in range(rows)]
            with Image.open(selected) as archived:
                if archived.size != (width, height):
                    raise ValueError("Archived visual has an unexpected size")
                px = archived.convert("RGB").load()
                samples = [[tuple(px[cx, cy])[:3] for cx in xs] for cy in ys]  # type: ignore[index]
        except (OSError, ValueError, IndexError, KeyError, TypeError) as exc:
            raise ValueError(f"View {index}: archived visual could not be sampled.") from exc
        return ({"index": index, "turn": selection["turn"], "frame": self._frame_number(selected),
                 "available_frames": len(paths),
                 "available_frame_range": [self._frame_number(paths[0]), self._frame_number(paths[-1])],
                 "region": {"x": x, "y": y, "width": w, "height": h},
                 "rows": rows, "columns": columns}, samples)
