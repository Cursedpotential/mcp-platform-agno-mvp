"""Framework-neutral request contract for the Workbench streaming chat.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.types.copilot import CopilotContext


class ChatMessagePart(BaseModel):
    """One AI SDK UI-message part; only text parts enter the model prompt."""

    type: str
    text: str | None = Field(default=None, max_length=100_000)


class ChatMessage(BaseModel):
    """UI-message shape accepted from Vercel AI SDK or plain clients."""

    id: str | None = None
    role: Literal["system", "user", "assistant"]
    parts: list[ChatMessagePart] = Field(default_factory=list, max_length=200)
    content: str | None = Field(default=None, max_length=100_000)

    def text_content(self) -> str:
        """Flatten text parts while retaining a plain-content compatibility door."""
        if self.parts:
            return "".join(part.text or "" for part in self.parts if part.type == "text")
        return self.content or ""


class ChatRequest(BaseModel):
    """Complete stateless chat request; history arrives on every turn."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=256)
    context: CopilotContext | None = None
