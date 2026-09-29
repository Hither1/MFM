from __future__ import annotations
import abc
from abc import abstractmethod
import json
import re
from loguru import logger
from typing import List
from pydantic import BaseModel, Field, conint, conlist, confloat, field_validator


class ActionState(BaseModel):

    back: conint(ge=0, le=1) = 0
    forward: conint(ge=0, le=1) = 0
    left: conint(ge=0, le=1) = 0
    right: conint(ge=0, le=1) = 0
    jump: conint(ge=0, le=1) = 0
    attack: conint(ge=0, le=1) = 0

    sneak: conint(ge=0, le=1) = 0
    sprint: conint(ge=0, le=1) = 0

    ESC: conint(ge=0, le=1) = 0
    swap_hands: conint(ge=0, le=1) = 0
    use: conint(ge=0, le=1) = 0
    inventory: conint(ge=0, le=1) = 0
    drop: conint(ge=0, le=1) = 0

    pick_item: conint(ge=0, le=1) = 0
    # camera = [pitch_delta, yaw_delta]
    # pitch_delta: [-90, 90]  (look up/down)
    # yaw_delta:   [-180, 180] (turn left/right — 180° full half-turn is valid)
    camera: List[float] = Field(default_factory=lambda: [0.0, 0.0])
    hotbars: conlist(conint(ge=0, le=1), min_length=9, max_length=9) = Field(default_factory=lambda: [0] * 9)

    @field_validator("camera")
    @classmethod
    def validate_camera(cls, v):
        if len(v) != 2:
            raise ValueError("camera must have exactly 2 elements [pitch_delta, yaw_delta]")
        pitch, yaw = float(v[0]), float(v[1])
        if not (-90.0 <= pitch <= 90.0):
            raise ValueError(f"camera[0] (pitch_delta) must be in [-90, 90], got {pitch}")
        # Normalize yaw to the equivalent shortest signed turn in [-180, 180]
        # (e.g. 270 -> -90) instead of rejecting values outside the canonical range.
        yaw = ((yaw + 180.0) % 360.0) - 180.0
        return [pitch, yaw]

    think: str = "I will continue my current plan."
    memory_update: str = ""

    class Config:
        validate_assignment = True


class BaseActionSpace(abc.ABC):
    def __init__(
        self,
        action_class: type
    ) -> None:
        self.action_space_name = action_class.__name__

    @abstractmethod
    def load_action(
        self,
        action_content: str | dict
    ) -> ActionState:
        raise NotImplementedError("BaseActionSpace is an abstract class, you need to implement subclass")

    def load_default_action(self) -> ActionState:
        return ActionState()

    def dump_action_to_dict(
        self,
        action: ActionState
    ) -> dict:
        return {
            "ESC": action.ESC,
            "attack": action.attack,
            "back": action.back,
            "forward": action.forward,
            "left": action.left,
            "right": action.right,
            "jump": action.jump,
            "camera": action.camera,
            "drop": action.drop,
            "hotbar.1": action.hotbars[0],
            "hotbar.2": action.hotbars[1],
            "hotbar.3": action.hotbars[2],
            "hotbar.4": action.hotbars[3],
            "hotbar.5": action.hotbars[4],
            "hotbar.6": action.hotbars[5],
            "hotbar.7": action.hotbars[6],
            "hotbar.8": action.hotbars[7],
            "hotbar.9": action.hotbars[8],
            "inventory": action.inventory,
            "pickItem": action.pick_item,
            "sneak": action.sneak,
            "sprint": action.sprint,
            "swapHands": action.swap_hands,
            "use": action.use,
        }

    def validate_action(
        self,
        action: ActionState
    ) -> bool:
        if action.sneak | action.sprint:
            if (action.forward | action.back | action.left | action.right) == 0:
                logger.warning(f"{self.action_space_name} validation failed: action.sneak or action.sprint must combine an arrow keys")
                return False

        if sum(action.hotbars) > 1:
            logger.warning(f"{self.action_space_name} validation failed: only one hotbar can be pressed.")
            return False

        return True


def extract_json_from_response(text: str) -> dict:
    """Robustly extract the action JSON dict from raw LLM output.

    Handles:
    1. Thinking-model output: strips <think>...</think> blocks first.
    2. Markdown code-fenced JSON: ```json ... ``` (may appear multiple times).
    3. Bare JSON object directly in the text.
    4. Llama-style Markdown sections: **Thought:** ... **Action:** ```json ... ``` **Memory Update:** ...

    Module-level so it can be reused by callers that need the full parsed
    dict (e.g. HypothesisAgent reading extra "hypotheses"/"plan" keys)
    without depending on a particular ActionSpace subclass.
    """
    # --- Step 1: strip <think>...</think> blocks (thinking models) ---
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # --- Step 2: try to extract a ```json ... ``` block that has all 3 required keys ---
    json_blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for candidate in reversed(json_blocks):  # prefer the last block
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "action" in parsed and "thought" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    # --- Step 3: try the last ``` ... ``` block that has all required keys ---
    raw_blocks = re.findall(r"```\s*(.*?)```", text, re.DOTALL)
    for candidate in reversed(raw_blocks):
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "action" in parsed and "thought" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    # --- Step 4: detect Llama-style Markdown sections ---
    thought_match = re.search(
        r'\*{0,2}[Tt]hought\*{0,2}:?\*{0,2}\s*(.*?)(?=\*{0,2}[Aa]ction|\Z)',
        text, re.DOTALL
    )
    action_match = re.search(
        r'\*{0,2}[Aa]ction\*{0,2}:?\*{0,2}.*?```(?:json)?\s*(\{.*?\})\s*```',
        text, re.DOTALL
    )
    if action_match is None:
        action_match = re.search(
            r'\*{0,2}[Aa]ction\*{0,2}:?\*{0,2}\s*(\{.*?\})',
            text, re.DOTALL
        )
    memory_match = re.search(
        r'\*{0,2}[Mm]emory[\s_][Uu]pdate\*{0,2}:?\*{0,2}\s*(.*?)(?=\n\*{1,2}[A-Z]|\Z)',
        text, re.DOTALL
    )

    if thought_match and action_match:
        thought = thought_match.group(1).strip()
        action_str = action_match.group(1).strip()
        memory = memory_match.group(1).strip() if memory_match else ""
        try:
            action_dict = json.loads(action_str)
            return {
                "thought": thought,
                "action": action_dict,
                "memory_update": memory,
            }
        except json.JSONDecodeError:
            pass

    # --- Step 5: find the first top-level { ... } object that has required keys ---
    pos = 0
    while True:
        brace_start = text.find("{", pos)
        if brace_start == -1:
            break
        depth = 0
        for i, ch in enumerate(text[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[brace_start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and "action" in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        pass
                    pos = i + 1
                    break
        else:
            break

    # --- Step 6: last resort – parse the whole stripped text ---
    return json.loads(text.strip())


class DefaultActionSpace(BaseActionSpace):
    def __init__(
        self
    ) -> None:
        super().__init__(DefaultActionSpace)

    @staticmethod
    def _extract_json_from_response(text: str) -> dict:
        return extract_json_from_response(text)

    def load_action(
        self,
        response_content: str | dict
    ) -> ActionState:
        action = ActionState()

        if isinstance(response_content, str):
            response_content = self._extract_json_from_response(response_content)
            action_content = response_content["action"]
            action.think = response_content["thought"]
            # Absent or null means "memory unchanged" (the compact response style sends the
            # memory only when it changes); the caller keeps its memory on an empty string.
            action.memory_update = response_content.get("memory_update") or ""

        for action_type, value in action_content.items():
            if "ESC" in action_type:
                action.ESC = value
            elif "attack" in action_type:
                action.attack = value
            elif "back" in action_type:
                action.back = value
            elif "drop" in action_type:
                action.drop = value
            elif "forward" in action_type:
                action.forward = value
            elif "inventory" in action_type:
                action.inventory = value
            elif "jump" in action_type:
                action.jump = value
            elif "left" in action_type:
                action.left = value
            elif "pickItem" in action_type:
                action.pick_item = value
            elif "right" in action_type:
                action.right = value
            elif "sneak" in action_type:
                action.sneak = value
            elif "sprint" in action_type:
                action.sprint = value
            elif "swapHands" in action_type:
                action.swap_hands = value
            elif "use" in action_type:
                action.use = value
            elif "camera" in action_type:
                action.camera = value
            elif "hotbar." in action_type:
                index = int(action_type[-1])
                action.hotbars[index - 1] = value

        if not self.validate_action(action):
            action = self.load_default_action()

        return action


# Alias used throughout the codebase
MinerRLActionSpace = DefaultActionSpace
