from functools import lru_cache
from typing import Any

from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from langfuse import get_client


@lru_cache(maxsize=1)
def get_langfuse_client() -> Any:
    """Return a process-wide Langfuse client (memoized)."""
    return get_client()


@lru_cache(maxsize=1)
def instrument_google_adk() -> bool:
    """Idempotently instrument Google ADK for OpenInference."""
    GoogleADKInstrumentor().instrument()
    return True


