"""`goal_image:`: the task's target is designated by a PICTURE, not by a phrase.

Why this exists. MrSteve's Long-Navigation ends with an image goal; our port replaced it
with a text designator ("the place where you saw a patch of ground burning") so the
prompt contract would stay identical across the arc/vista/logbook paths. That swap was
right for a cross-arm comparison and wrong for a modality one: it removed the single
property that made the task multimodal, so a text-only memory could answer it in full.

What the cue is. Not a shipped PNG -- the world is generated, so no fixed picture would
match it -- and not a canonical render either. It is **the agent's own past view**,
captured while it stood at the landmark with no goal at all, and handed back much later:
"go back to where this picture was taken." That is the cleanest form of the question this
file is for. A memory that stores frames can compare the cue against what it holds; a
memory that stores only words has to have written down, at the time and with no reason
to, whatever the picture would later turn out to show.

The capture is guarded. The agent is teleported to the landmark and looks wherever it
was already looking, so the frame at any single step can be sky, or the inside of a
block. `_degenerate` rejects a frame with almost no variation and the capture retries
through a window, keeping the last frame that carries detail. The step actually used is
written into the report, because a run whose cue turned out to be a picture of the sky
measured nothing and has to be discardable on the evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

#: Below this per-channel standard deviation a frame is flat -- sky, a wall pressed
#: against the camera, the inside of a block. Minecraft's sky is not perfectly uniform
#: (clouds, gradient), so this is deliberately low: it rejects the useless, not the dull.
_FLAT_STD = 12.0


def _degenerate(arr: "np.ndarray") -> bool:
    try:
        return float(np.asarray(arr, dtype=np.float32).std()) < _FLAT_STD
    except Exception:
        return False


class GoalImage:
    """Capture one frame in a window, then serve it once its milestone is live.

    `spec` is the task config's `goal_image:` mapping:
        step        first step at which a capture is attempted
        window      how many steps past `step` to keep retrying for a non-flat frame
        every       retry interval inside the window
        milestone   the goal identity the picture designates
    """

    def __init__(self, spec: dict[str, Any], attach_dir: Path) -> None:
        self.step = int(spec["step"])
        self.window = int(spec.get("window", 1200))
        self.every = max(1, int(spec.get("every", 100)))
        self.milestone = str(spec["milestone"])
        self.path = attach_dir / "goal.png"
        self.captured_at: int | None = None
        self.flat_rejects = 0
        self.served = 0

    # -- capture ---------------------------------------------------------------

    def _should_try(self, step: int) -> bool:
        if step < self.step or step > self.step + self.window:
            return False
        if self.captured_at is None:
            return True
        # Already have one: keep improving only while still inside the window, and
        # only on the retry cadence.
        return (step - self.step) % self.every == 0

    def maybe_capture(self, step: int, pov) -> None:
        """Save the current view as the cue if this step is in the window.

        Keeps the last non-flat frame seen inside the window, so a capture that opened
        on the sky is replaced by one that opened on the ground.
        """
        if pov is None or not self._should_try(step):
            return
        try:
            arr = np.asarray(pov)
            if _degenerate(arr):
                self.flat_rejects += 1
                return
            from PIL import Image
            if arr.dtype != np.uint8:
                arr = arr.astype(np.uint8)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(arr).save(self.path, format="PNG")
            self.captured_at = int(step)
            logger.info(f"[goal-image] cue captured at step {step} -> {self.path}")
        except Exception as e:                                  # pragma: no cover
            logger.warning(f"[goal-image] capture failed at step {step}: {e}")

    # -- serve -----------------------------------------------------------------

    def live(self, ledger) -> bool:
        """True when the picture should be in front of the model: the goal it names is
        open (past its `not_before`, prerequisites met) and not yet achieved."""
        if self.captured_at is None or not self.path.exists():
            return False
        if self.milestone in getattr(ledger, "achieved", {}):
            return False
        return bool(ledger.eligible(self.milestone))

    def serve(self, ledger) -> Path | None:
        if not self.live(ledger):
            return None
        self.served += 1
        return self.path

    #: The line that goes in the turn prompt beside the picture.
    NOTE = ("**Your goal is a PLACE, and it is shown to you as a PICTURE.** The last "
            "image attached to this turn is a view recorded earlier in this same "
            "episode, from where you were standing at the time. Go back to the place it "
            "was taken from. Nothing names it for you -- no coordinates, no description "
            "-- so work from what the picture shows and what you remember of going there.")

    def audit(self) -> dict[str, Any]:
        return {"captured_at": self.captured_at, "milestone": self.milestone,
                "flat_rejects": self.flat_rejects, "served": self.served,
                "window": [self.step, self.step + self.window]}
