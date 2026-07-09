"""Phase 1 live check — real provider, real network round-trip (no dummies)."""

import agno
from agno.agent import Agent

from server.core.settings import build_model

m = build_model()
print(f"agno={agno.__version__} provider_class={type(m).__name__} model_id={m.id}")

agent = Agent(model=m, telemetry=False, markdown=False)
resp = agent.run("Reply with exactly the single word: PONG")
content = (getattr(resp, "content", None) or str(resp)).strip()
print(f"LIVE_REPLY: {content[:160]}")
