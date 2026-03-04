"""
Guardrails Service
Analyzes inputs and outputs for the routing agent using Guardrails Hub validators.

Optional LLM fallback (global):
- Set env var GUARDRAILS_LLM_MODEL to enable LLM fallback for RestrictToTopic.
  Examples:
    GUARDRAILS_LLM_MODEL="gemini-1.5-flash"
    GUARDRAILS_LLM_MODEL="gemini-1.5-pro"

Required hub installs (examples):
  guardrails hub install hub://guardrails/detect_pii
  guardrails hub install hub://guardrails/secrets_present
  guardrails hub install hub://guardrails/toxic_language
  guardrails hub install hub://guardrails/gibberish_text
  guardrails hub install hub://tryolabs/restricttotopic
"""

from __future__ import annotations

import os
from typing import Optional, Callable, Tuple

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from guardrails import Guard
from guardrails.validators import (
    Validator,
    register_validator,
    ValidationResult,
    PassResult,
    FailResult,
)
from guardrails.hub import (
    DetectPII,
    RestrictToTopic,
    ToxicLanguage,
    SecretsPresent,
    GibberishText,
)

app = FastAPI(
    title="Guardrails Service",
    description="Validation service for routing agent inputs and outputs using Guardrails Hub validators.",
    version="1.4.0",
)

# --- CORS (frontend at :5173 calling this service at :8005) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ValidationRequest(BaseModel):
    message: str


class ValidationResponse(BaseModel):
    is_safe: bool
    filtered_message: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------
# Dynamic Threshold Configurations
# ---------------------------------------------------------

class ThresholdState:
    restrict_to_topic: float = 0.25
    toxic_language: float = 0.6
    gibberish_text: float = 0.6

thresholds = ThresholdState()

class ThresholdUpdateRequest(BaseModel):
    restrict_to_topic: Optional[float] = None
    toxic_language: Optional[float] = None
    gibberish_text: Optional[float] = None

class ThresholdResponse(BaseModel):
    restrict_to_topic: float
    toxic_language: float
    gibberish_text: float


# ---------------------------------------------------------
# Custom Validators (rule-based)
# ---------------------------------------------------------

@register_validator(name="is-safe-input", data_type="string")
class IsSafeInput(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        dangerous_keywords = ["drop table", "ignore previous instructions", "bypass"]
        if any(keyword in value.lower() for keyword in dangerous_keywords):
            return FailResult(error_message="Potentially malicious input detected.")
        return PassResult()


@register_validator(name="enforce-anonymous-mode", data_type="string")
class EnforceAnonymousMode(Validator):
    """
    NOTE: This blocks account-specific requests. If your retail agent truly supports
    authenticated access, you should REMOVE this validator or gate it behind auth.
    """
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        account_keywords = ["my balance", "rejected", "my loan", "my account", "my transaction"]
        if any(kw in value.lower() for kw in account_keywords):
            return FailResult(
                error_message="For account-specific inquiries, please contact a bank representative through official channels."
            )
        return PassResult()


@register_validator(name="block-financial-advisory", data_type="string")
class BlockFinancialAdvisory(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        advisory_keywords = ["best for me", "should i invest", "avoid kyc", "bypass limits", "recommend"]
        if any(kw in value.lower() for kw in advisory_keywords):
            return FailResult(
                error_message="I can provide general product information, but for personalized financial advice, please consult a bank representative."
            )
        return PassResult()


@register_validator(name="escalation-trigger", data_type="string")
class EscalationTrigger(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        escalation_keywords = ["fraud", "scam", "stolen", "legal", "lawsuit", "complaint", "sue", "attorney", "lawyer"]
        if any(kw in value.lower() for kw in escalation_keywords):
            print(f"[ESCALATION EVENT] Triggered by user input: {value}")
            return FailResult(
                error_message="Escalation: Your query requires specialized assistance. Please contact our front desk or a live agent immediately."
            )
        return PassResult()


@register_validator(name="is-safe-output", data_type="string")
class IsSafeOutput(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        if "credit card number" in value.lower():
            return FailResult(error_message="Sensitive PII detected in output.")
        return PassResult()


# ---------------------------------------------------------
# Hub Validator Configuration
# ---------------------------------------------------------

PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN"]

# Broader, more realistic banking topics/phrases + greetings/small talk so basic chat isn't blocked
# RestrictToTopic works best with short semantic topic labels (categories),
# not greetings/keywords/phrases.
VALID_TOPICS = [
    "bank accounts",
    "online banking access",
    "login and password reset",
    "account balances and transactions",
    "deposits",
    "payments and transfers",
    "wire transfers",
    "bank cards",
    "fees and charges",
    "branch and atm information",
    "routing number and swift/iban",
    "opening a new account",
    "loans and mortgages",
]


def _build_global_gemini_llm_callable() -> Tuple[Optional[str], Optional[Callable[[str], str]]]:
    """
    Builds a Gemini LLM callable if GUARDRAILS_LLM_MODEL is set.
    Returns (model_name, callable) or (None, None).

    Requires:
      - google-generativeai installed
      - GOOGLE_API_KEY set
    """
    model = (os.getenv("GUARDRAILS_LLM_MODEL") or "").strip()
    if not model:
        return None, None

    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GUARDRAILS_LLM_MODEL is set but GOOGLE_API_KEY is missing.")

    import google.generativeai as genai  # type: ignore

    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model)

    def llm_callable(prompt: str) -> str:
        resp = gemini_model.generate_content(prompt)
        # Be defensive: sometimes SDK returns None text
        return getattr(resp, "text", None) or ""

    return model, llm_callable


input_guard: Optional[Guard] = None
output_guard: Optional[Guard] = None


@app.on_event("startup")
def startup_event() -> None:
    """
    Initialize guards once at startup.
    Uses Hub validators + rule-based validators.
    Includes optional Gemini LLM fallback for RestrictToTopic if GUARDRAILS_LLM_MODEL is set.
    """
    global input_guard, output_guard

    llm_model, llm_callable = _build_global_gemini_llm_callable()
    use_llm = llm_callable is not None

    # INPUT
    # Uses BOTH fixes:
    #  1) expanded VALID_TOPICS including greetings/small talk
    #  2) RestrictToTopic is soft (on_fail="noop") so casual chat isn't blocked
        # Decide whether RestrictToTopic should hard-block or soft-fail based on slider
    restrict_on_fail = "exception" if thresholds.restrict_to_topic >= 0.5 else "noop"

    input_guard = (
        Guard()
        .use(
            IsSafeInput(on_fail="exception"),
            EnforceAnonymousMode(on_fail="exception"),
            BlockFinancialAdvisory(on_fail="exception"),
            EscalationTrigger(on_fail="exception"),

            RestrictToTopic(
                valid_topics=VALID_TOPICS,
                invalid_topics=[],
                disable_classifier=False,
                disable_llm=not use_llm,
                llm_callable=llm_callable if use_llm else None,
                model_threshold=thresholds.restrict_to_topic,
                on_fail=restrict_on_fail,
            ),

            DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"),

            # Don't hard-block on secrets for normal user messages
            SecretsPresent(on_fail="exception"),

            ToxicLanguage(threshold=thresholds.toxic_language, validation_method="sentence", on_fail="exception"),
            GibberishText(threshold=thresholds.gibberish_text, validation_method="sentence", on_fail="exception"),
        )
    )


    # OUTPUT (keep strict)
    output_guard = (
        Guard()
        .use(
            DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"),
            SecretsPresent(on_fail="exception"),
            IsSafeOutput(on_fail="exception"),
        )
    )

    if llm_model:
        print(f"[GUARDRAILS] RestrictToTopic LLM fallback enabled via GUARDRAILS_LLM_MODEL={llm_model!r}")
    else:
        print("[GUARDRAILS] RestrictToTopic LLM fallback disabled (GUARDRAILS_LLM_MODEL not set)")


def _extract_reason(exc: Exception) -> str:
    msg = str(exc).strip()
    return msg or "Validation failed."

@app.post("/check_input", response_model=ValidationResponse)
def check_input(payload: ValidationRequest) -> ValidationResponse:
    msg = payload.message.strip().lower()
    if msg in {"hey", "hi", "hello", "yo", "sup", "what's up", "whats up"}:
        return ValidationResponse(is_safe=True, filtered_message=payload.message, reason=None)

    global input_guard
    if input_guard is None:
        return ValidationResponse(is_safe=False, filtered_message=None, reason="Guards not initialized.")

    try:
        outcome = input_guard.validate(payload.message)

        # If ALL validators passed normally
        if outcome.validation_passed:
            return ValidationResponse(
                is_safe=True,
                filtered_message=outcome.validated_output,
                reason=None,
            )

        # If validation failed but was configured as a soft-fail ("noop"),
        # allow the message through unchanged.
        return ValidationResponse(
            is_safe=True,
            filtered_message=payload.message,
            reason=None,
        )

    except Exception as e:
        # Hard fail ("exception") or unexpected error => block
        return ValidationResponse(is_safe=False, filtered_message=None, reason=_extract_reason(e))


@app.post("/check_output", response_model=ValidationResponse)
def check_output(payload: ValidationRequest) -> ValidationResponse:
    global output_guard
    if output_guard is None:
        return ValidationResponse(is_safe=False, filtered_message=None, reason="Guards not initialized.")

    try:
        outcome = output_guard.validate(payload.message)
        return ValidationResponse(
            is_safe=bool(outcome.validation_passed),
            filtered_message=outcome.validated_output if outcome.validation_passed else None,
            reason=None,
        )
    except Exception as e:
        return ValidationResponse(is_safe=False, filtered_message=None, reason=_extract_reason(e))


@app.get("/thresholds", response_model=ThresholdResponse)
def get_thresholds() -> ThresholdResponse:
    return ThresholdResponse(
        restrict_to_topic=thresholds.restrict_to_topic,
        toxic_language=thresholds.toxic_language,
        gibberish_text=thresholds.gibberish_text
    )


@app.post("/thresholds", response_model=ThresholdResponse)
def update_thresholds(payload: ThresholdUpdateRequest) -> ThresholdResponse:
    if payload.restrict_to_topic is not None:
        thresholds.restrict_to_topic = payload.restrict_to_topic
    if payload.toxic_language is not None:
        thresholds.toxic_language = payload.toxic_language
    if payload.gibberish_text is not None:
        thresholds.gibberish_text = payload.gibberish_text

    # Re-initialize guards with new thresholds
    startup_event()

    return ThresholdResponse(
        restrict_to_topic=thresholds.restrict_to_topic,
        toxic_language=thresholds.toxic_language,
        gibberish_text=thresholds.gibberish_text
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    print("[SERVER] Starting Guardrails Service...")
    port = int(os.getenv("PORT", "8005"))

    uvicorn.run(
        "backend.services.guardrails.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()