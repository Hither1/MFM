"""Extract and store target grids for ARC-AGI-3 games to enable cell-level accuracy.

BACKGROUND
----------
In online mode the API only returns FrameData.frame — the camera's 64×64 rendered
view of the current game state.  The target (expected output) grid is never
exposed: the game server validates answers internally.

In NORMAL mode (OperationMode.NORMAL), the Arcade client downloads the game Python
source to environment_files/<game_id>/<version>/<class>.py and runs it locally.
Once the Python class is available we can instantiate the game, inspect its
_clean_levels[i]._data / sprite layers, and pull out the target grid.

This script does all of that once per game version and writes the results to
target_grids/<game_id>.json.  Subsequent eval runs load that file and compute
cell-level accuracy against FrameData.frame[-1] (the most-recent camera frame).

USAGE
-----
    # Download + extract targets for one or more games
    python extract_targets.py --games ls20 cd82 bp35
    python extract_targets.py --games ls20   # single game
    python extract_targets.py --list-cached  # show already-extracted games

CELL-LEVEL ACCURACY NOTES
--------------------------
Not all ARC-AGI 3 games expose a comparable "target grid":
  - PLACE-type games   : player fills a grid → target is a fixed 2-D grid
  - Navigation games   : player moves an entity → no single target grid applies
  - Mixed games        : partial target (e.g. only certain cells matter)

This script tries four extraction strategies in order and records which succeeded:
  1. level._data key search (common keys: target, goal, output, solution)
  2. Sprites tagged "target" / "goal" / "solution" (picks lowest non-background layer)
  3. Camera interface labelled "target" (RenderableUserDisplay subclasses)
  4. Fallback: None — cell accuracy will be unavailable for this game

REQUIREMENTS
------------
    ARC_API_KEY environment variable must be set.
    pip install arc-agi>=0.9.8
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Background color index — cells with this value are treated as empty
_BACKGROUND = 5


import numpy as np


def _pixels_to_list(pix: Any) -> list[list[int]]:
    if hasattr(pix, "tolist"):
        return pix.tolist()
    return [list(row) for row in pix]


def _is_blank(pixels: Any) -> bool:
    """True if every non-transparent pixel (-1) is the background colour (0 or 5)."""
    arr = np.array(pixels) if not hasattr(pixels, "shape") else pixels
    visible = arr[arr >= 0]
    return len(visible) == 0 or bool(np.all((visible == 0) | (visible == 5)))


def _extract_level_target(game, level_idx: int) -> dict[str, Any]:
    """Extract target grid for one level.

    Strategy: within the clean level, look for a pair of sprites with the
    same shape where one is blank (all-zero/background — the player's
    workspace) and one is non-trivial (the target pattern to match).

    This mirrors what the actual win-check does (e.g. cd82's wvrremwltt
    which calls np.array_equal on the two sprites).  Games without such
    a pair (navigation games, physics puzzles) return target=None.
    """
    try:
        level = game._clean_levels[level_idx]
    except (AttributeError, IndexError):
        return {"strategy": None, "target": None, "error": "level not accessible"}

    sprites = level.get_sprites() if hasattr(level, "get_sprites") else []

    # Group sprites by (rows, cols) shape — only consider 2-D pixel grids
    shape_groups: dict[tuple[int, int], list] = {}
    for s in sprites:
        pix = getattr(s, "pixels", None)
        if pix is None:
            continue
        arr = np.array(pix) if not hasattr(pix, "shape") else pix
        if arr.ndim != 2:
            continue
        key = (int(arr.shape[0]), int(arr.shape[1]))
        shape_groups.setdefault(key, []).append((s, arr))

    def _is_dense_target(arr: np.ndarray, min_visible_frac: float = 0.5) -> bool:
        """Return True only if the sprite has enough visible, non-background pixels
        to be a real game target (not a decorative icon or HUD element)."""
        total = arr.size
        visible = arr[(arr >= 0) & (arr != 5)]  # exclude transparent (-1,-2) and bg (5)
        return len(visible) >= 4 and len(visible) / total >= min_visible_frac

    # Look for a shape group with exactly one blank workspace and a small number of
    # dense non-blank candidates.  Require the group is small (<=3 distinct sprites
    # by name) so we don't match game-grid tiles that repeat dozens of times.
    for shape, group in shape_groups.items():
        distinct_names = {s.name for s, _ in group}
        if len(distinct_names) > 3:
            continue  # too many sprites of this shape → tile grid, not workspace

        blanks        = [(s, arr) for s, arr in group if _is_blank(arr)]
        dense_targets = [(s, arr) for s, arr in group if not _is_blank(arr) and _is_dense_target(arr)]
        if len(blanks) == 1 and dense_targets:
            # Pick the target with the most unique colours (richest pattern)
            target_s, target_arr = max(dense_targets, key=lambda x: int(np.unique(x[1][x[1] >= 0]).size))
            workspace_s, _ = blanks[0]
            return {
                "strategy": "blank_nonblank_pair",
                "target": _pixels_to_list(target_arr),
                "target_sprite": target_s.name,
                "workspace_sprite": workspace_s.name,
                "shape": list(shape),
            }

    # No matching pair — record sprite summary for debugging
    return {
        "strategy": None,
        "target": None,
        "sprite_count": len(sprites),
        "shapes": [list(k) for k in shape_groups.keys()],
        "sprite_names": [s.name for s in sprites],
    }


def _extract_goal_pattern_targets(game) -> list[dict[str, Any]]:
    """For games with a 'current piece must match goal pattern' mechanic (e.g. ls20).

    Calls on_set_level() for each level — which configures the kvynsvxbpi goal-
    pattern sprites from level data (GoalRotation, GoalColor, kvynsvxbpi index) —
    then reads those sprite pixels as the per-level targets.

    The first goal's pattern is stored as 'target' for cell-level accuracy.
    All goals' patterns are stored in 'all_goal_patterns'.
    """
    original_idx = getattr(game, "_current_level_index", 0)
    n = len(getattr(game, "_clean_levels", []))
    results: list[dict[str, Any]] = []

    for i in range(n):
        try:
            game._current_level_index = i
            game.on_set_level(game._clean_levels[i])  # param ignored; uses self.current_level

            goal_sprites = getattr(game, "srgbthxut", [])
            goal_patterns: list[list[list[int]]] = []
            for spr in goal_sprites:
                pix = spr.pixels
                arr = np.array(pix) if not hasattr(pix, "shape") else pix
                goal_patterns.append(_pixels_to_list(arr))

            target = goal_patterns[0] if goal_patterns else None
            results.append({
                "level_index": i,
                "strategy": "goal_patterns_on_set_level",
                # target = first goal's configured pattern sprite (small, e.g. 3×3).
                # NOTE: cell_accuracy_applicable=False because this sprite appears
                # at an arbitrary position in the 64×64 rendered frame, so top-left
                # aligned comparison against the frame is not meaningful.
                "target": target,
                "cell_accuracy_applicable": False,
                "all_goal_patterns": goal_patterns,
                "n_goals": len(goal_patterns),
                "shape": list(np.array(target).shape) if target else None,
            })
        except Exception as exc:
            results.append({
                "level_index": i,
                "strategy": None,
                "target": None,
                "error": str(exc),
            })

    # Restore original level so the game object stays consistent
    try:
        game._current_level_index = original_idx
        game.on_set_level(game._clean_levels[original_idx])
    except Exception:
        pass

    return results


def _game_uses_goal_patterns(game) -> bool:
    """Return True if game has the 'align piece to goal pattern' mechanic."""
    return (
        hasattr(game, "ijessuuig")           # template sprite list (ls20)
        and hasattr(game, "on_set_level")
        and bool(getattr(game, "_clean_levels", []))
        and any(
            getattr(lv, "get_data", lambda k: None)("kvynsvxbpi") is not None
            for lv in game._clean_levels[:1]
        )
    )


def _game_uses_canvas_target(game) -> bool:
    """True for re86-style games: each level contains exactly one large (≥32×32)
    non-blank sprite that VARIES between levels — it is the pixel-comparison
    reference in the win condition (the player must assemble movable pieces to
    match this target pattern)."""
    levels = getattr(game, "_clean_levels", [])
    n = len(levels)
    if n < 2:
        return False

    shape_ref = None
    prev_arr = None
    for lv in levels[:min(n, 4)]:
        sprites_in_level = lv.get_sprites() if hasattr(lv, "get_sprites") else []
        large_nonblank = []
        for s in sprites_in_level:
            pix = getattr(s, "pixels", None)
            if pix is None:
                continue
            arr = np.array(pix) if not hasattr(pix, "shape") else pix
            if arr.ndim != 2:
                continue
            if min(arr.shape) >= 32 and not _is_blank(arr):
                large_nonblank.append(arr)
        if len(large_nonblank) != 1:
            return False
        arr = large_nonblank[0]
        if shape_ref is None:
            shape_ref = arr.shape
        elif arr.shape != shape_ref:
            return False  # inconsistent shape across levels
        prev_arr = arr if prev_arr is None else prev_arr
        if prev_arr is not arr and np.array_equal(prev_arr, arr):
            return False  # same sprite in every level → background, not per-level target
        prev_arr = arr

    return shape_ref is not None


def _extract_canvas_targets(game) -> list[dict[str, Any]]:
    """Extract the per-level canvas-sized target sprite (re86-style).

    Each clean level contains exactly one large non-blank sprite whose pixels
    are the direct pixel-comparison reference used in the win condition.
    """
    results = []
    for i, lv in enumerate(getattr(game, "_clean_levels", [])):
        try:
            sprites_in_level = lv.get_sprites() if hasattr(lv, "get_sprites") else []
            found = None
            for s in sprites_in_level:
                pix = getattr(s, "pixels", None)
                if pix is None:
                    continue
                arr = np.array(pix) if not hasattr(pix, "shape") else pix
                if arr.ndim == 2 and min(arr.shape) >= 32 and not _is_blank(arr):
                    found = (s, arr)
                    break
            if found is None:
                results.append({
                    "level_index": i,
                    "strategy": None,
                    "target": None,
                    "error": "no canvas-sized non-blank sprite found",
                })
            else:
                s, arr = found
                results.append({
                    "level_index": i,
                    "strategy": "canvas_target_sprite",
                    "target": _pixels_to_list(arr),
                    "target_sprite": s.name,
                    "cell_accuracy_applicable": True,
                    "shape": list(arr.shape),
                })
        except Exception as exc:
            results.append({
                "level_index": i,
                "strategy": None,
                "target": None,
                "error": str(exc),
            })
    return results


def _game_is_placeholder_sprite(game) -> bool:
    """True for custom-renderer games (bp35, lf52) where each ARCBaseGame Level
    holds only a single 1×1 dummy sprite — the real game state lives inside a
    per-level engine object that the game creates in on_set_level()."""
    levels = getattr(game, "_clean_levels", [])
    if not levels:
        return False
    for lv in levels[:2]:
        sprites = lv.get_sprites() if hasattr(lv, "get_sprites") else []
        if len(sprites) != 1:
            return False
        pix = getattr(sprites[0], "pixels", None)
        if pix is None:
            return False
        arr = np.array(pix)
        if arr.shape != (1, 1):
            return False
    return True


def _render_initial_frame(game) -> Optional[list[list[int]]]:
    """Render the current level's initial state to a 64×64 frame.

    Tries two methods in order:
    1. Standard ARCBaseGame camera: game._camera.render(sprites) → works for
       any sprite-based game (ar25, cd82, ls20, and most unknown games).
    2. Custom engine scan: looks for an instance attribute with a no-arg
       render() returning a list of 2-D arrays → works for bp35/lf52-style
       games that embed a per-level render engine.

    Returns None if both methods fail.
    """
    # Method 1: standard camera
    cam = getattr(game, "_camera", None)
    if cam is not None and hasattr(cam, "render"):
        try:
            lv = game.current_level
            sprites = lv.get_sprites() if hasattr(lv, "get_sprites") else []
            result = cam.render(sprites)
            arr = np.array(result)
            if arr.ndim == 2:
                return _pixels_to_list(arr)
        except Exception:
            pass

    # Method 2: custom engine attribute (bp35/lf52-style)
    for attr_val in vars(game).values():
        if attr_val is game or not hasattr(attr_val, "render"):
            continue
        try:
            frames = attr_val.render()
            if isinstance(frames, list) and frames:
                arr = np.array(frames[0])
                if arr.ndim == 2:
                    return _pixels_to_list(arr)
        except Exception:
            pass

    return None


def _extract_initial_render_targets(game) -> list[dict[str, Any]]:
    """Universal fallback for any game that doesn't fit a specific strategy.

    Calls on_set_level() for each level and renders the initial game state
    via the best available render method (camera or embedded engine).

    No pixel-comparison target is available for these games, so
    cell_accuracy_applicable is False.  The initial_frame is useful for
    debugging and as visual context in prompts.
    """
    original_idx = getattr(game, "_current_level_index", 0)
    n = len(getattr(game, "_clean_levels", []))
    results: list[dict[str, Any]] = []

    for i in range(n):
        try:
            game._current_level_index = i
            game.on_set_level(game._clean_levels[i])

            initial_frame = _render_initial_frame(game)

            results.append({
                "level_index": i,
                "strategy": "initial_render" if initial_frame else "no_target",
                "target": None,
                "initial_frame": initial_frame,
                "cell_accuracy_applicable": False,
                "shape": list(np.array(initial_frame).shape) if initial_frame else None,
            })
        except Exception as exc:
            results.append({
                "level_index": i,
                "strategy": None,
                "target": None,
                "error": str(exc),
            })

    # Restore original level
    try:
        game._current_level_index = original_idx
        game.on_set_level(game._clean_levels[original_idx])
    except Exception:
        pass

    return results


def extract_targets_for_game(
    game_id: str,
    arcade,
    output_dir: Path,
) -> dict[str, Any]:
    """Download game, instantiate it, extract all level targets."""
    from arc_agi import OperationMode

    logger.info("Processing game: %s", game_id)

    env_wrapper = arcade.make(game_id, seed=0, scorecard_id="extract_targets_dummy")
    if env_wrapper is None:
        return {"game_id": game_id, "error": "arcade.make() returned None"}

    # Access the underlying ARCBaseGame instance (LocalEnvironmentWrapper._game)
    game = getattr(env_wrapper, "_game", None)
    if game is None:
        return {"game_id": game_id, "error": "LocalEnvironmentWrapper has no _game attribute"}

    n_levels = len(getattr(game, "_clean_levels", []))
    if n_levels == 0:
        return {"game_id": game_id, "error": "game has no levels"}

    # --- Choose extraction strategy ---
    # 1. ls20-style: player piece must match a per-level goal pattern sprite
    if _game_uses_goal_patterns(game):
        logger.info("  Detected goal-pattern game (ls20-style) — using on_set_level strategy")
        level_targets = _extract_goal_pattern_targets(game)
        for result in level_targets:
            i = result["level_index"]
            strategy = result.get("strategy") or "FAILED"
            logger.info("  Level %d: strategy=%s  target=%s  n_goals=%s",
                        i, strategy,
                        (f"{len(result['target'])}×{len(result['target'][0])}"
                         if result.get("target") else "None"),
                        result.get("n_goals", "?"))

    # 2. cd82-style: blank workspace sprite paired with non-blank target sprite.
    #    Levels where it fails (e.g. tutorial level 0) fall back to initial_render.
    elif any(_extract_level_target(game, i).get("strategy") for i in range(min(n_levels, 2))):
        # Pre-compute initial renders for the fallback (one on_set_level pass)
        render_fallbacks = {r["level_index"]: r for r in _extract_initial_render_targets(game)}
        level_targets = []
        for i in range(n_levels):
            result = _extract_level_target(game, i)
            result["level_index"] = i
            if result.get("strategy") is None and i in render_fallbacks:
                result = render_fallbacks[i]   # use initial render for failed levels
            level_targets.append(result)
            strategy = result.get("strategy") or "FAILED"
            logger.info("  Level %d: strategy=%s  target=%s",
                        i, strategy,
                        f"{len(result['target'])}×{len(result['target'][0])}" if result.get("target") else "None")

    # 3. re86-style: one large per-level-varying non-blank sprite = the pixel target
    elif _game_uses_canvas_target(game):
        logger.info("  Detected canvas-target game (re86-style) — one large target sprite per level")
        level_targets = _extract_canvas_targets(game)
        for result in level_targets:
            i = result["level_index"]
            strategy = result.get("strategy") or "FAILED"
            logger.info("  Level %d: strategy=%s  target=%s",
                        i, strategy,
                        f"{len(result['target'])}×{len(result['target'][0])}" if result.get("target") else "None")

    # 4. Universal fallback: render initial game state (covers bp35/lf52/ar25/unknown)
    else:
        logger.info("  Using initial-render fallback (navigation/physics/unknown game)")
        level_targets = _extract_initial_render_targets(game)
        for result in level_targets:
            i = result["level_index"]
            strategy = result.get("strategy") or "FAILED"
            has_frame = result.get("initial_frame") is not None
            logger.info("  Level %d: strategy=%s  initial_frame=%s",
                        i, strategy, has_frame)

    available_actions = list(getattr(game, "_available_actions", []))
    try:
        from arcengine import GameAction
        action_names = [GameAction.from_id(a).name for a in available_actions]
    except Exception:
        action_names = [str(a) for a in available_actions]

    record = {
        "game_id": game_id,
        "n_levels": n_levels,
        "available_actions": action_names,
        "has_place_action": "PLACE" in action_names,
        "levels": level_targets,
    }

    out_path = output_dir / f"{game_id}.json"
    out_path.write_text(json.dumps(record, indent=2))
    logger.info("Saved targets → %s", out_path)
    return record


# ---------------------------------------------------------------------------
# Position-based partial progress (computed live from game state)
# ---------------------------------------------------------------------------

def _progress_s5i5(game) -> float:
    """Fraction of mover pieces currently at a goal position."""
    try:
        movers = game.current_level.get_sprites_by_tag("0087vvmblxkzdi")
        goals  = game.current_level.get_sprites_by_tag("0064ocqkuqacti")
        if not movers:
            return 1.0
        matched = sum(
            1 for m in movers
            if any(m.x == g.x and m.y == g.y for g in goals)
        )
        return matched / len(movers)
    except Exception:
        return 0.0


def _progress_lp85(game) -> float:
    """Fraction of piece+goal pairings satisfied.

    Win requires:
      - each bghvgbtwcb sprite has a 'goal'   sprite at (x+1, y+1)
      - each fdgmtkfrxl sprite has a 'goal-o' sprite at (x+1, y+1)
    """
    try:
        lv = game.current_level
        movers_a = lv.get_sprites_by_tag("bghvgbtwcb")
        movers_b = lv.get_sprites_by_tag("fdgmtkfrxl")
        total = len(movers_a) + len(movers_b)
        if total == 0:
            return 1.0
        matched = (
            sum(1 for m in movers_a if lv.get_sprite_at(m.x + 1, m.y + 1, "goal")   is not None)
          + sum(1 for m in movers_b if lv.get_sprite_at(m.x + 1, m.y + 1, "goal-o") is not None)
        )
        return matched / total
    except Exception:
        return 0.0


def _progress_ka59(game) -> float:
    """Fraction of nested-fit constraints satisfied.

    Win requires:
      - each 0010xzmuziohuf has a 0022vrxelxosfy nested inside it (x+1,y+1, size-2)
      - each 0027jbgxilrocf has a 0001uqqokjrptk nested inside it
    """
    try:
        lv = game.current_level
        group_a = lv.get_sprites_by_tag("0010xzmuziohuf")
        goals_a = lv.get_sprites_by_tag("0022vrxelxosfy")
        group_b = lv.get_sprites_by_tag("0027jbgxilrocf")
        goals_b = lv.get_sprites_by_tag("0001uqqokjrptk")
        total = len(group_a) + len(group_b)
        if total == 0:
            return 1.0

        def _fits(outer, inners):
            return any(
                g.x == outer.x + 1
                and g.y == outer.y + 1
                and g.height == outer.height - 2
                and g.width  == outer.width  - 2
                for g in inners
            )

        matched = (
            sum(1 for s in group_a if _fits(s, goals_a))
          + sum(1 for s in group_b if _fits(s, goals_b))
        )
        return matched / total
    except Exception:
        return 0.0


def _progress_tu93(game) -> float:
    """Fraction of arrow pieces currently at an exit tile."""
    try:
        movers = game.current_level.get_sprites_by_tag("0017unajnymcki")
        exits  = game.current_level.get_sprites_by_tag("0015msvpvzxhqf")
        if not movers:
            return 1.0
        matched = sum(
            1 for m in movers
            if any(m.x == e.x and m.y == e.y for e in exits)
        )
        return matched / len(movers)
    except Exception:
        return 0.0


def read_ls20_game_state(game) -> Optional[dict]:
    """Read ls20 player/goal state from the live game object.

    Returns a dict with player position, goal positions, shape/color/rotation
    state, and remaining steps — or None if game is not an ls20 instance.
    Called from both the agent (for prompt injection) and the progress metric.
    """
    try:
        px, py = int(game.gudziatsk.x), int(game.gudziatsk.y)
        cell_w = int(game.gisrhqpee)  # sprite width = one movement step (5 px)
        goals = []
        for i, goal_spr in enumerate(game.plrpelhym):
            req_shape    = int(game.ldxlnycps[i])
            req_color    = int(game.yjdexjsoa[i])
            req_rot_idx  = int(game.ehwheiwsk[i])
            req_rotation = int(game.dhksvilbb[req_rot_idx])
            state_match = (
                game.fwckfzsyc == req_shape
                and game.hiaauhahz == req_color
                and game.cklxociuu == req_rot_idx
            )
            dx_cells = (int(goal_spr.x) - px) // cell_w
            dy_cells = (int(goal_spr.y) - py) // cell_w
            goals.append({
                "pos": (int(goal_spr.x), int(goal_spr.y)),
                "req_shape":   req_shape,
                "req_color":   req_color,
                "req_rotation": req_rotation,
                "state_match": state_match,
                "dist_cells":  abs(dx_cells) + abs(dy_cells),
            })
        remaining = getattr(
            getattr(game, "_step_counter_ui", None), "current_steps", None
        )
        return {
            "player_pos":      (px, py),
            "player_shape":    int(game.fwckfzsyc),
            "player_color":    int(game.hiaauhahz),
            "player_rotation": int(game.dhksvilbb[game.cklxociuu]),
            "cell_size": cell_w,
            "goals": goals,
            "remaining_steps": int(remaining) if remaining is not None else None,
        }
    except Exception:
        return None


def _progress_ls20(game) -> float:
    """Progress metric for ls20: distance to nearest goal + state match.

    0.5 weight: how close the player is (in grid cells) to the nearest goal.
    0.5 weight: whether the player's shape/color/rotation matches any goal.
    """
    state = read_ls20_game_state(game)
    if state is None or not state["goals"]:
        return 0.0
    state_match = any(g["state_match"] for g in state["goals"])
    best_dist   = min(g["dist_cells"] for g in state["goals"])
    # 64×64 grid, cell_size=5 → ~12 cells per axis; max useful dist ≈ 24 cells
    dist_progress = max(0.0, 1.0 - best_dist / 24.0)
    return 0.5 * dist_progress + (0.5 if state_match else 0.0)


# Map game_id → progress function for games that support live position tracking
_POSITION_PROGRESS_FNS: dict[str, Any] = {
    "s5i5": _progress_s5i5,
    "lp85": _progress_lp85,
    "ka59": _progress_ka59,
    "tu93": _progress_tu93,
    "ls20": _progress_ls20,
}


def compute_position_progress(game_id: str, game) -> Optional[float]:
    """Compute partial win-condition progress for position-based games.

    Called during live evaluation with the actual game object (only available
    in OperationMode.NORMAL).  Returns a float in [0, 1]:
      1.0 = all win-condition constraints satisfied (game should trigger win next step)
      0.0 = no constraints satisfied
      None = not supported for this game_id
    """
    fn = _POSITION_PROGRESS_FNS.get(game_id)
    if fn is None:
        return None
    return fn(game)


# ---------------------------------------------------------------------------
# Cell accuracy (loaded from pre-extracted JSON)
# ---------------------------------------------------------------------------

def load_target_grids(game_id: str, targets_dir: str = "target_grids") -> Optional[list[Optional[dict]]]:
    """Load pre-extracted target info for a game.

    Returns a list of per-level dicts with keys:
        target   - 2-D list[list[int]] target grid (or None)
        shape    - [rows, cols]
        strategy - extraction strategy name
    Returns None if target_grids/<game_id>.json does not exist.
    """
    path = Path(targets_dir) / f"{game_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("levels", [])
    except Exception:
        return None


def compute_cell_accuracy(
    frame_grid: list[list[int]],
    target_grid: list[list[int]],
) -> float:
    """Fraction of non-background target cells that match in frame_grid.

    Compares only cells where the target is non-background (not 0 or 5).
    Returns 0.0 if no non-background cells exist in the target.

    NOTE: frame_grid is the full 64×64 camera render, which may include UI
    elements.  The workspace region within it may be offset.  For a more
    precise comparison, instantiate the game in offline mode and read the
    workspace sprite pixels directly rather than the rendered camera frame.
    """
    if not target_grid or not frame_grid:
        return 0.0

    t_arr = np.array(target_grid)
    rows, cols = t_arr.shape

    # Extract the matching region from the frame (top-left aligned)
    f_rows = len(frame_grid)
    f_cols = max((len(r) for r in frame_grid), default=0)
    f_arr = np.full((f_rows, f_cols), _BACKGROUND, dtype=np.int64)
    for r, row in enumerate(frame_grid):
        for c, v in enumerate(row):
            f_arr[r, c] = v

    # Crop to target size
    compare_rows = min(rows, f_rows)
    compare_cols = min(cols, f_cols)
    t_crop = t_arr[:compare_rows, :compare_cols]
    f_crop = f_arr[:compare_rows, :compare_cols]

    # Compare only cells where target is a real color (>0, != background).
    # Exclude transparent (-1, -2) and background (0, 5) cells.
    mask = (t_crop > 0) & (t_crop != _BACKGROUND)
    total = int(mask.sum())
    if total == 0:
        return 0.0
    matching = int(np.sum(f_crop[mask] == t_crop[mask]))
    return matching / total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def list_cached(output_dir: Path) -> None:
    files = sorted(output_dir.glob("*.json"))
    if not files:
        print(f"No extracted targets in {output_dir}")
        return
    print(f"\nCached targets in {output_dir}/:")
    for f in files:
        try:
            d = json.loads(f.read_text())
            n = d.get("n_levels", "?")
            has_place = d.get("has_place_action", False)
            levels = d.get("levels", [])
            n_processed = sum(1 for lvl in levels if lvl.get("strategy") is not None)
            n_cell_acc = sum(1 for lvl in levels
                            if lvl.get("target") is not None and lvl.get("cell_accuracy_applicable", True))
            strats = {lvl.get("strategy") for lvl in levels if lvl.get("strategy")}
            print(f"  {f.stem:<10}  levels={n}  processed={n_processed}/{n}  "
                  f"cell_acc={n_cell_acc}/{n}  strategies={strats}")
        except Exception as e:
            print(f"  {f.stem}  (error reading: {e})")
    print()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract and store ARC-AGI-3 target grids for cell-level accuracy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--games", nargs="+", metavar="GAME_ID",
                   help="Game IDs to process (e.g. ls20 cd82 bp35)")
    p.add_argument("--output-dir", default="target_grids",
                   help="Directory to write per-game JSON files (default: target_grids)")
    p.add_argument("--arc-url", default="https://three.arcprize.org",
                   help="ARC API base URL")
    p.add_argument("--list-cached", action="store_true",
                   help="List already-extracted games and exit")
    return p


def main() -> None:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.list_cached:
        list_cached(output_dir)
        return

    if not args.games:
        print("ERROR: specify --games GAME_ID [GAME_ID ...] or --list-cached")
        sys.exit(1)

    arc_api_key = os.environ.get("ARC_API_KEY", "").strip()
    if not arc_api_key:
        print("ERROR: ARC_API_KEY not set.")
        sys.exit(1)

    try:
        from arc_agi import Arcade, OperationMode
    except ImportError:
        print("ERROR: arc-agi not installed.  Run: pip install arc-agi>=0.9.8")
        sys.exit(1)

    # NORMAL mode: downloads Python game files to environment_files/ then runs locally
    arcade = Arcade(
        arc_api_key=arc_api_key,
        arc_base_url=args.arc_url,
        operation_mode=OperationMode.NORMAL,
    )

    results = []
    for game_id in args.games:
        try:
            r = extract_targets_for_game(game_id, arcade, output_dir)
            results.append(r)
        except Exception as e:
            logger.error("Failed to process %s: %s", game_id, e)
            results.append({"game_id": game_id, "error": str(e)})

    print("\n=== Summary ===")
    for r in results:
        gid = r.get("game_id", "?")
        if "error" in r:
            print(f"  {gid}: ERROR — {r['error']}")
        else:
            n = r.get("n_levels", 0)
            levels = r.get("levels", [])
            n_processed = sum(1 for lvl in levels if lvl.get("strategy") is not None)
            n_cell_acc = sum(1 for lvl in levels
                            if lvl.get("target") is not None and lvl.get("cell_accuracy_applicable", True))
            strats = {lvl.get("strategy") for lvl in levels if lvl.get("strategy")}
            print(f"  {gid}: {n_processed}/{n} levels processed  "
                  f"({n_cell_acc} with cell accuracy)  strategies={strats}")


if __name__ == "__main__":
    main()
