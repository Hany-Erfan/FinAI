from contextvars import ContextVar

# Sub-agent attempt tracking
SUBAGENT_ATTEMPTS: ContextVar[dict[str, list[float]]] = ContextVar("subagent_attempts", default={})
