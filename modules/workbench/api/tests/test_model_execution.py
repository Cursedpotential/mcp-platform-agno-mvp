"""Observed adapter-contract tests for Workbench model execution.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from agno.models.message import Message

from app.service.model_providers import run_classification, run_sentiment


class FakeAgnoModel:
    """Implements Agno 2.8's aresponse API and deliberately has no arun."""

    def __init__(self, content: str) -> None:
        self.id = "fake-model"
        self.temperature: float | None = None
        self.max_tokens: int | None = None
        self.content = content
        self.messages: list[Message] = []

    async def aresponse(self, messages: list[Message], **_kwargs: Any) -> Any:
        self.messages = messages
        return SimpleNamespace(content=self.content)


def test_classification_uses_installed_agno_aresponse_contract() -> None:
    model = FakeAgnoModel('{"category":"legal","confidence":0.9,"reasoning":"filing"}')

    result = asyncio.run(
        run_classification(
            model,
            "Motion for parenting time",
            ["legal", "other"],
            temperature=0.2,
            max_tokens=321,
        )
    )

    assert result[:3] == ("legal", 0.9, "filing")
    assert model.temperature == 0.2
    assert model.max_tokens == 321
    assert [message.role for message in model.messages] == ["system", "user"]


def test_sentiment_uses_installed_agno_aresponse_contract() -> None:
    model = FakeAgnoModel('{"sentiment":"mixed","score":0.1,"emotions":{"trust":0.4},"reasoning":"conflicted"}')

    result = asyncio.run(
        run_sentiment(
            model,
            "I want to trust this but remain worried.",
            temperature=0.1,
            max_tokens=222,
        )
    )

    assert result[:4] == ("mixed", 0.1, {"trust": 0.4}, "conflicted")
    assert model.temperature == 0.1
    assert model.max_tokens == 222
