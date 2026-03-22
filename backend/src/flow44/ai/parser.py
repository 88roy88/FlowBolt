"""Incremental parser for flowArtifact XML streaming responses.

The parser processes text arriving character-by-character and emits callbacks
as soon as complete actions are detected.  It does NOT require a well-formed
XML document up-front — it works with partial / streaming input.

XML format handled::

    <flowArtifact id="..." title="...">
      <flowAction type="file" filePath="src/App.tsx">
        file content here
      </flowAction>
    </flowArtifact>
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import Enum, auto


class _State(Enum):
    TEXT = auto()
    IN_ARTIFACT = auto()
    IN_ACTION_BODY = auto()

# TODO: think about this:
# A. I want to move to structured output anyway
# B. This doesnt validate that the xml was closed and that we got the full file content.

class ActionParser:
    """Feed-based streaming parser for flowArtifact XML.

    Callbacks
    ---------
    on_text(text: str)
        Fired for text outside any ``<flowArtifact>`` block.
    on_file_action(path: str, content: str)
        Fired when a complete ``<flowAction type="file">`` is parsed.
    """

    def __init__(
        self,
        on_text: Callable[[str], None] | None = None,
        on_file_action: Callable[[str, str], None] | None = None,
    ) -> None:
        self.on_text = on_text or (lambda _t: None)
        self.on_file_action = on_file_action or (lambda _p, _c: None)

        self._buffer: str = ""
        self._state: _State = _State.TEXT
        self._action_file_path: str = ""
        self._action_body: str = ""

    def feed(self, chunk: str) -> None:
        """Feed the next chunk of streamed text into the parser."""
        self._buffer += chunk
        self._process()

    _ARTIFACT_OPEN = re.compile(r"<flowArtifact\b[^>]*>", re.DOTALL)
    _ARTIFACT_CLOSE = "</flowArtifact>"
    _ACTION_OPEN = re.compile(
        r'<flowAction\s+type="file"(?:\s+filePath="(?P<path>[^"]*)")?[^>]*>',
        re.DOTALL,
    )
    _ACTION_CLOSE = "</flowAction>"

    def _process(self) -> None:
        while self._buffer:
            if self._state is _State.TEXT:
                idx = self._buffer.find("<flowArtifact")
                if idx == -1:
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self.on_text(self._buffer[:safe])
                        self._buffer = self._buffer[safe:]
                    return
                else:
                    if idx > 0:
                        self.on_text(self._buffer[:idx])
                    m = self._ARTIFACT_OPEN.match(self._buffer, idx)
                    if m is None:
                        return
                    self._buffer = self._buffer[m.end():]
                    self._state = _State.IN_ARTIFACT

            elif self._state is _State.IN_ARTIFACT:
                action_idx = self._buffer.find("<flowAction")
                close_idx = self._buffer.find(self._ARTIFACT_CLOSE)

                if close_idx != -1 and (action_idx == -1 or close_idx < action_idx):
                    self._buffer = self._buffer[close_idx + len(self._ARTIFACT_CLOSE):]
                    self._state = _State.TEXT
                    continue

                if action_idx == -1:
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self._buffer = self._buffer[safe:]
                    return

                m = self._ACTION_OPEN.match(self._buffer, action_idx)
                if m is None:
                    return
                self._action_file_path = m.group("path") or ""
                self._action_body = ""
                self._buffer = self._buffer[m.end():]
                self._state = _State.IN_ACTION_BODY

            elif self._state is _State.IN_ACTION_BODY:
                close_idx = self._buffer.find(self._ACTION_CLOSE)
                if close_idx == -1:
                    safe = max(0, len(self._buffer) - 20)
                    if safe > 0:
                        self._action_body += self._buffer[:safe]
                        self._buffer = self._buffer[safe:]
                    return

                self._action_body += self._buffer[:close_idx]
                self._buffer = self._buffer[close_idx + len(self._ACTION_CLOSE):]

                self.on_file_action(self._action_file_path, self._action_body.strip())

                self._action_file_path = ""
                self._action_body = ""
                self._state = _State.IN_ARTIFACT

    def flush(self) -> None:
        """Flush any remaining buffered text (call at end of stream)."""
        if self._buffer:
            if self._state is _State.TEXT:
                self.on_text(self._buffer)
            self._buffer = ""
