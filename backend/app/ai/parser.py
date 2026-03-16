"""Incremental parser for boltArtifact XML streaming responses.

The parser processes text arriving character-by-character and emits callbacks
as soon as complete actions are detected.  It does NOT require a well-formed
XML document up-front — it works with partial / streaming input.

XML format handled::

    <boltArtifact id="..." title="...">
      <boltAction type="file" filePath="src/App.tsx">
        file content here
      </boltAction>
      <boltAction type="shell">
        npm install some-package
      </boltAction>
    </boltArtifact>
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import Enum, auto


class _State(Enum):
    TEXT = auto()
    IN_ARTIFACT = auto()
    IN_ACTION_TAG = auto()
    IN_ACTION_BODY = auto()


class ActionParser:
    """Feed-based streaming parser for boltArtifact XML.

    Callbacks
    ---------
    on_text(text: str)
        Fired for text outside any ``<boltArtifact>`` block.
    on_file_action(path: str, content: str)
        Fired when a complete ``<boltAction type="file">`` is parsed.
    on_shell_action(command: str)
        Fired when a complete ``<boltAction type="shell">`` is parsed.
    """

    def __init__(
        self,
        on_text: Callable[[str], None] | None = None,
        on_file_action: Callable[[str, str], None] | None = None,
        on_shell_action: Callable[[str], None] | None = None,
    ) -> None:
        self.on_text = on_text or (lambda _t: None)
        self.on_file_action = on_file_action or (lambda _p, _c: None)
        self.on_shell_action = on_shell_action or (lambda _c: None)

        self._buffer: str = ""
        self._state: _State = _State.TEXT
        self._text_buffer: str = ""
        self._action_type: str = ""
        self._action_file_path: str = ""
        self._action_body: str = ""

    # ------------------------------------------------------------------

    def feed(self, chunk: str) -> None:
        """Feed the next chunk of streamed text into the parser."""
        self._buffer += chunk
        self._process()

    # ------------------------------------------------------------------

    _ARTIFACT_OPEN = re.compile(r"<boltArtifact\b[^>]*>", re.DOTALL)
    _ARTIFACT_CLOSE = "</boltArtifact>"
    _ACTION_OPEN = re.compile(
        r'<boltAction\s+type="(?P<type>[^"]+)"(?:\s+filePath="(?P<path>[^"]*)")?[^>]*>',
        re.DOTALL,
    )
    _ACTION_CLOSE = "</boltAction>"

    def _process(self) -> None:  # noqa: C901 — complexity justified by state machine
        while self._buffer:
            if self._state is _State.TEXT:
                idx = self._buffer.find("<boltArtifact")
                if idx == -1:
                    # No opening tag yet — but keep a small tail in case we
                    # are in the middle of receiving "<boltArti…"
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self.on_text(self._buffer[:safe])
                        self._buffer = self._buffer[safe:]
                    return  # wait for more data
                else:
                    # Emit text before the tag
                    if idx > 0:
                        self.on_text(self._buffer[:idx])
                    # Try to match the full opening tag
                    m = self._ARTIFACT_OPEN.match(self._buffer, idx)
                    if m is None:
                        return  # incomplete tag — wait
                    self._buffer = self._buffer[m.end():]
                    self._state = _State.IN_ARTIFACT

            elif self._state is _State.IN_ARTIFACT:
                # Look for <boltAction …> or </boltArtifact>
                action_idx = self._buffer.find("<boltAction")
                close_idx = self._buffer.find(self._ARTIFACT_CLOSE)

                if close_idx != -1 and (action_idx == -1 or close_idx < action_idx):
                    # Artifact closed
                    self._buffer = self._buffer[close_idx + len(self._ARTIFACT_CLOSE):]
                    self._state = _State.TEXT
                    continue

                if action_idx == -1:
                    # Keep a tail buffer for partial tag detection
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self._buffer = self._buffer[safe:]
                    return

                m = self._ACTION_OPEN.match(self._buffer, action_idx)
                if m is None:
                    return  # incomplete tag
                self._action_type = m.group("type")
                self._action_file_path = m.group("path") or ""
                self._action_body = ""
                self._buffer = self._buffer[m.end():]
                self._state = _State.IN_ACTION_BODY

            elif self._state is _State.IN_ACTION_BODY:
                close_idx = self._buffer.find(self._ACTION_CLOSE)
                if close_idx == -1:
                    # Accumulate body, keep tail for partial close-tag detection
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self._action_body += self._buffer[:safe]
                        self._buffer = self._buffer[safe:]
                    return

                self._action_body += self._buffer[:close_idx]
                self._buffer = self._buffer[close_idx + len(self._ACTION_CLOSE):]

                # Emit the completed action
                body = self._action_body.strip()
                if self._action_type == "file":
                    self.on_file_action(self._action_file_path, body)
                elif self._action_type == "shell":
                    self.on_shell_action(body)

                self._action_type = ""
                self._action_file_path = ""
                self._action_body = ""
                self._state = _State.IN_ARTIFACT

    def flush(self) -> None:
        """Flush any remaining buffered text (call at end of stream)."""
        if self._buffer:
            if self._state is _State.TEXT:
                self.on_text(self._buffer)
            self._buffer = ""
