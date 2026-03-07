"""
DataMasker – replaces sensitive PII with labelled placeholders before
content is written to the database or sent to any external AI model.

Masking is applied at TWO points in the pipeline:
  1. host_agent.py  – before saving each message to the DB
                      (Gemini ChatSession still receives the original so
                       it can reason correctly)
  2. summary_agent.py – before the transcript is sent to the summary
                        Gemini call (second safety layer, even though
                        DB messages are already masked)

Placeholders use the form  <TYPE_n>  so they survive round-trips
through Gemini without being confused with real content.

Extend PATTERNS or subclass DataMasker to add domain-specific patterns
(e.g. internal ticket IDs, employee numbers).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MaskPattern:
    name: str           # Used in the placeholder, e.g. "EMAIL" → <EMAIL_1>
    pattern: str        # Raw regex string
    flags: int = re.IGNORECASE


# ---------------------------------------------------------------------------
# Default pattern library – extend as needed
# ---------------------------------------------------------------------------
DEFAULT_PATTERNS: list[MaskPattern] = [
    MaskPattern(
        name="CARD_NUMBER",
        # for credit/debit cards
        pattern=r"\b(?:\d[ -]*?){13,19}\b",
    ),
    MaskPattern(
        name="BANK_ACCOUNT",
        # Bank account
        pattern=r"\b\d{3}[- ]\d{2}[- ]\d{4}\b",
    ),
    MaskPattern(
        name="NATIONAL_ID",
        # National ID for egypt
        pattern=r"\b[23]\d{13}\b",
    ),
    MaskPattern(
        # Generic IBAN for EU and Egypt
        name="IBAN",
        pattern=r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b',
    ),
    MaskPattern(
        name="EMAIL",
        pattern=r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    ),
    MaskPattern(
        name="PHONE",
        # Covers local numbers or ones with country codes
        pattern=r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b",
    ),
    MaskPattern(
        name="DATE_OF_BIRTH",
        # DD/MM/YYYY, MM-DD-YYYY, YYYY.MM.DD
        pattern=r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b",
    ),
]


class DataMasker:
    """
    Applies regex-based PII masking to text.

    Args:
        patterns: List of MaskPattern instances. Defaults to DEFAULT_PATTERNS.
        keep_count: When True (default) the placeholder includes a counter
                    per pattern type so multiple occurrences are
                    distinguishable: <EMAIL_1>, <EMAIL_2> …
                    Set to False for a flat placeholder: <EMAIL>.

    Example::

        masker = DataMasker()
        safe = masker.mask("Call me at +1 555-123-4567 or john@example.com")
        # → "Call me at <PHONE_1> or <EMAIL_1>"
        original = masker.unmask(safe)  # only works in the same masker instance
    """

    def __init__(
        self,
        patterns: Optional[list[MaskPattern]] = None,
        keep_count: bool = True,
    ):
        self._patterns = patterns if patterns is not None else DEFAULT_PATTERNS
        self._keep_count = keep_count
        # Compile once for performance
        self._compiled = [
            (p.name, re.compile(p.pattern, p.flags))
            for p in self._patterns
        ]
        # Reverse-lookup for unmask: placeholder → original value
        self._vault: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask(self, text: str) -> str:
        """
        Return a copy of *text* with all recognised PII replaced by
        placeholders.  The mapping is stored internally so that
        :meth:`unmask` can reverse it within the same instance lifetime.
        """
        counters: dict[str, int] = {}

        def replace(match: re.Match, name: str) -> str:
            original = match.group(0)
            counters[name] = counters.get(name, 0) + 1
            placeholder = (
                f"<{name}_{counters[name]}>" if self._keep_count else f"<{name}>"
            )
            self._vault[placeholder] = original
            return placeholder

        result = text
        # Apply patterns in order: more specific first (CC before generic phone)
        for name, compiled in self._compiled:
            result = compiled.sub(lambda m, n=name: replace(m, n), result)

        return result

    def unmask(self, text: str) -> str:
        """
        Reverse previously applied masking within this session.
        Only works if the same DataMasker instance was used to mask.
        """
        result = text
        for placeholder, original in self._vault.items():
            result = result.replace(placeholder, original)
        return result

    def mask_dict(self, data: dict) -> dict:
        """Recursively mask string values in a dict (e.g. metadata)."""
        out = {}
        for k, v in data.items():
            if isinstance(v, str):
                out[k] = self.mask(v)
            elif isinstance(v, dict):
                out[k] = self.mask_dict(v)
            elif isinstance(v, list):
                out[k] = [self.mask(i) if isinstance(i, str) else i for i in v]
            else:
                out[k] = v
        return out