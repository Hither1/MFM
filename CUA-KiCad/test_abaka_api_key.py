"""Quick one-shot check that ABAKA_API_KEY is valid (single API call).

Plain text check:
    python test_abaka_api_key.py [model]

Vision check (send an image + question):
    python test_abaka_api_key.py [model] --image path/to/frame.png [--question "..."]

Note: reasoning models (e.g. gemini-3.5-flash) burn thousands of tokens on
hidden reasoning before emitting visible text, especially on vision prompts.
If the response comes back empty, raise --max-tokens (16000+ for
gemini-3.5-flash on an image).
"""
import argparse
import base64
import os
import sys

from openai import OpenAI

_ABAKA_BASE_URL = "https://app-us.ppapi.ai/v1"

DEFAULT_IMAGE = "logs/arc_agi3/ls20/test_frame.png"
DEFAULT_QUESTION = (
    "This is a frame from the ARC-AGI-3 maze game 'ls20'. The player is the "
    "blue arrow-shaped tile. Plan a route (as a sequence of UP/DOWN/LEFT/RIGHT "
    "moves) from the player's current position to the white '+' shaped tile, "
    "avoiding walls."
)


def _image_to_data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def check_abaka_key(
    model: str = "gpt-4.1-mini",
    image_path: str | None = None,
    question: str = DEFAULT_QUESTION,
    max_tokens: int = 1024,
) -> bool:
    key = os.environ.get("ABAKA_API_KEY", "").strip()
    if not key:
        print("ERROR: ABAKA_API_KEY not set in environment.")
        return False

    if image_path:
        content = [
            {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
            {"type": "text", "text": question},
        ]
    else:
        content = "Reply with just: ok"

    client = OpenAI(base_url=_ABAKA_BASE_URL, api_key=key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens if image_path else 5,
        )
        text = resp.choices[0].message.content
        print(f"OK: ABAKA_API_KEY works. Response: {text!r}")
        return True
    except Exception as e:
        print(f"FAILED: ABAKA_API_KEY request errored: {e}")
        return False


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("model", nargs="?", default="gpt-4.1-mini")
    p.add_argument("--image", nargs="?", const=DEFAULT_IMAGE, default=None,
                   help=f"Path to an image to send (bare --image uses {DEFAULT_IMAGE}).")
    p.add_argument("--question", default=DEFAULT_QUESTION)
    p.add_argument("--max-tokens", type=int, default=1024)
    args = p.parse_args()

    ok = check_abaka_key(args.model, args.image, args.question, args.max_tokens)
    sys.exit(0 if ok else 1)
