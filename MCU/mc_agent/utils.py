"""Utility helpers for the Minecraft agent.

Functions:
  - convert_buffer_to_base64_images  – encode a list of numpy frames to base64 PNG strings
  - deco_retry_on_ratelimit          – decorator: retry on HTTP 429 / rate-limit errors
  - deco_retry_exponential           – decorator: retry with exponential back-off
"""
from __future__ import annotations
import base64
import io
import time
import random
from functools import wraps

import numpy as np
from PIL import Image
from loguru import logger


# ---------------------------------------------------------------------------
# Image conversion
# ---------------------------------------------------------------------------

def downsample_pov(img: Image.Image) -> Image.Image:
    """Halve a frame wider than 256 px, to save tokens and stay within context limits.

    Every arm's frames go through here, so per-frame fidelity is one setting rather than
    a property of the arm. The direct agents send 20 frames a step and need the saving;
    PRO-LONG sends one and does not -- but a sharper frame for one arm is an uncontrolled
    difference in the table they share, and the arm axis is meant to be the *number* of
    frames and what is done with them, not how many pixels each one carries.
    """
    if img.size[0] > 256:
        img = img.resize((img.size[0] // 2, img.size[1] // 2), Image.Resampling.LANCZOS)
    return img


def convert_buffer_to_base64_images(frame_buffer: list[np.ndarray]) -> list[bytes]:
    """Encode a list of numpy RGB frames to base64-encoded PNG strings."""
    base64_images = []
    for i, pov_image in enumerate(frame_buffer):
        try:
            img = downsample_pov(Image.fromarray(pov_image))

            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            base64_images.append(base64_image)
        except Exception as e:
            logger.error(f"Failed to encode frame {i} to base64: {e}")
            continue
    return base64_images


# ---------------------------------------------------------------------------
# Retry decorators
# ---------------------------------------------------------------------------

def deco_retry_on_ratelimit(max_retries: int = 10, wait_seconds: int = 60):
    """Retry a function when a rate-limit (HTTP 429) error is encountered.

    Non-rate-limit exceptions are re-raised immediately without retrying.

    Args:
        max_retries:   Maximum number of retry attempts after the first failure.
        wait_seconds:  Fixed wait time in seconds between retries.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    exc_str = str(e)
                    is_rate_limit = (
                        "429" in exc_str
                        or "rate limit" in exc_str.lower()
                        or "RateLimitError" in type(e).__name__
                        or "每分钟请求次数超过限制" in exc_str
                    )
                    if not is_rate_limit or i >= max_retries:
                        raise
                    logger.warning(
                        f"Attempt {i + 1}/{max_retries} failed for '{func.__name__}' "
                        f"(rate limit): {e}. Waiting {wait_seconds}s before retry..."
                    )
                    time.sleep(wait_seconds)
        return wrapper
    return decorator


def deco_retry_exponential(max_retries: int = 3, initial_sleep_seconds: int = 2):
    """Retry a function with exponential backoff and jitter.

    Args:
        max_retries:           Maximum number of retries.
        initial_sleep_seconds: Initial sleep time; doubles on each retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == max_retries - 1:
                        logger.error(f"Function '{func.__name__}' failed after {max_retries} retries.")
                        raise

                    sleep_time = (initial_sleep_seconds * (2 ** i)) + random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {i + 1}/{max_retries} failed for '{func.__name__}': {e}. "
                        f"Retrying in {sleep_time:.2f} seconds..."
                    )
                    time.sleep(sleep_time)
            raise Exception(f"Function '{func.__name__}' failed after {max_retries} retries.")
        return wrapper
    return decorator
