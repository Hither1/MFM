"""The rendezvous between the model's `play` and the environment's step.

Two threads, one action at a time:

    model thread (the codex app-server driver, inside the `play` tool handler)
        outcome = channel.play(action)          blocks until the environment reports

    environment thread (the benchmark's step: MCU `next_action`, KiCad `predict`)
        action = channel.take(timeout)          blocks until the model has called play
        ... the environment runs the action over one or many ticks ...
        channel.deliver(outcome)                unblocks `play` with what happened

`close(outcome)` ends the episode: a waiting or later `play` gets `outcome` at once (a
terminal result), and `take` returns None at once. Nothing here interprets the action
or the outcome; they are whatever the benchmark's bridge puts in.
"""
from __future__ import annotations

import threading
from typing import Any


class ActionChannel:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._action: Any = None
        self._has_action = False
        self._outcome: Any = None
        self._has_outcome = False
        self._closed = False
        self._final: Any = None
        self.plays = 0
        self.deliveries = 0

    # -- model side -------------------------------------------------------------------

    def play(self, action: Any) -> Any:
        """Hand `action` to the environment and wait for its outcome."""
        with self._cv:
            if self._closed:
                return self._final
            while self._has_action:
                # Two plays cannot be in flight: the model thread is single, so this
                # only happens if a previous play was abandoned by an interrupted turn
                # before the environment took it. The newer call supersedes it.
                self._has_action = False
                self._action = None
            self._action = action
            self._has_action = True
            self._has_outcome = False
            self.plays += 1
            self._cv.notify_all()
            while not self._has_outcome and not self._closed:
                self._cv.wait()
            if self._has_outcome:
                self._has_outcome = False
                outcome, self._outcome = self._outcome, None
                return outcome
            return self._final

    def pending(self) -> bool:
        """Is a play waiting for its outcome (taken or not)?"""
        with self._cv:
            return self._has_action or self._taken

    # -- environment side -------------------------------------------------------------

    _taken = False

    def take(self, timeout: float | None) -> Any:
        """The next action, or None when none arrived within `timeout` (or the channel
        is closed). Once taken, the play is owed a `deliver`."""
        with self._cv:
            if self._closed:
                return None
            if not self._has_action:
                self._cv.wait(timeout=timeout)
            if not self._has_action:
                return None
            self._has_action = False
            self._taken = True
            action, self._action = self._action, None
            return action

    def waiting(self) -> bool:
        """Has the model called play and the environment not yet taken it?"""
        with self._cv:
            return self._has_action

    def deliver(self, outcome: Any) -> bool:
        """Give the taken play its outcome. False when no play was owed one."""
        with self._cv:
            if not self._taken:
                return False
            self._taken = False
            self._outcome = outcome
            self._has_outcome = True
            self.deliveries += 1
            self._cv.notify_all()
            return True

    def owed(self) -> bool:
        with self._cv:
            return self._taken

    def close(self, final: Any) -> None:
        with self._cv:
            self._closed = True
            self._final = final
            self._has_action = False
            self._taken = False
            self._cv.notify_all()

    @property
    def closed(self) -> bool:
        with self._cv:
            return self._closed
