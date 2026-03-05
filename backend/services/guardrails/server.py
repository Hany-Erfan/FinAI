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
  guardrails hub install hub://tryolabs/restricttotopic
"""

from __future__ import annotations

import os
from typing import Optional, Callable, Tuple, List

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
    SecretsPresent,
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
# Dynamic Configurations
# ---------------------------------------------------------

class GuardrailsConfigState:
    is_safe_input: bool = True
    enforce_anonymous_mode: bool = True
    block_financial_advisory: bool = True
    escalation_trigger: bool = True
    restrict_to_topic: bool = True
    detect_pii_input: bool = True
    secrets_present_input: bool = True
    toxic_language: bool = True

    detect_pii_output: bool = True
    secrets_present_output: bool = True
    is_safe_output: bool = True

    valid_topics: List[str] = [
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

config = GuardrailsConfigState()

class GuardrailsConfigRequest(BaseModel):
    is_safe_input: Optional[bool] = None
    enforce_anonymous_mode: Optional[bool] = None
    block_financial_advisory: Optional[bool] = None
    escalation_trigger: Optional[bool] = None
    restrict_to_topic: Optional[bool] = None
    detect_pii_input: Optional[bool] = None
    secrets_present_input: Optional[bool] = None
    toxic_language: Optional[bool] = None
    detect_pii_output: Optional[bool] = None
    secrets_present_output: Optional[bool] = None
    is_safe_output: Optional[bool] = None
    valid_topics: Optional[List[str]] = None

class GuardrailsConfigResponse(BaseModel):
    is_safe_input: bool
    enforce_anonymous_mode: bool
    block_financial_advisory: bool
    escalation_trigger: bool
    restrict_to_topic: bool
    detect_pii_input: bool
    secrets_present_input: bool
    toxic_language: bool
    detect_pii_output: bool
    secrets_present_output: bool
    is_safe_output: bool
    valid_topics: List[str]


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


@register_validator(name="llm-toxic", data_type="string")
class LlmToxic(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        llm = (metadata or {}).get("llm_callable")

        # If no LLM callable is configured, don't block traffic here.
        # (Keep behavior minimal; rely on other validators.)
        if llm is None:
            return PassResult()

        prompt = (
            "You are a safety classifier. Analyze the following user text and decide if it contains toxic language "
            "(insults, harassment, hate, profanity directed at a person/group, threats). "
            "Return ONLY one token: 'TOXIC' or 'OK'.\n\n"
            f"TEXT:\n{value}\n"
        )

        try:
            result = (llm(prompt) or "").strip().upper()
        except Exception as e:
            return FailResult(error_message=f"LLM toxicity check failed: {type(e).__name__}: {e}")

        if result.startswith("TOXIC"):
            return FailResult(error_message="Toxic language detected (LLM multilingual).")

        return PassResult()


# ---------------------------------------------------------
# Hub Validator Configuration
# ---------------------------------------------------------

PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN"]


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

    def llm_callable(prompt: str = "", messages=None, **kwargs) -> str:
        # Guardrails may call llm_callable with either a raw prompt OR chat-style messages.
        # Support both to avoid silent failures / signature mismatches.
        if messages:
            prompt = "\n".join(
                m.get("content", "") if isinstance(m, dict) else str(m)
                for m in messages
            )

        print(f"[GUARDRAILS][LLM] Calling Gemini model={model!r} prompt_len={len(prompt)}")
        try:
            resp = gemini_model.generate_content(prompt)
            # Be defensive: sometimes SDK returns None text
            text = (getattr(resp, "text", None) or "").strip()
            print(f"[GUARDRAILS][LLM] Gemini response_len={len(text)}")
            return text
        except Exception as e:
            print(f"[GUARDRAILS][LLM][ERROR] Gemini call failed: {type(e).__name__}: {e}")
            raise

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

    input_validators = []
    output_validators = []

    if config.is_safe_input:
        input_validators.append(IsSafeInput(on_fail="exception"))
    if config.enforce_anonymous_mode:
        input_validators.append(EnforceAnonymousMode(on_fail="exception"))
    if config.block_financial_advisory:
        input_validators.append(BlockFinancialAdvisory(on_fail="exception"))
    if config.escalation_trigger:
        input_validators.append(EscalationTrigger(on_fail="exception"))
    if config.restrict_to_topic:
        input_validators.append(RestrictToTopic(
            valid_topics=config.valid_topics,
            invalid_topics=[],
            disable_classifier=False,
            disable_llm=not use_llm,
            llm_callable=llm_callable if use_llm else None,
            model_threshold=0.5,
            on_fail="exception",
        ))
    if config.detect_pii_input:
        input_validators.append(DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"))
    if config.secrets_present_input:
        input_validators.append(SecretsPresent(on_fail="exception"))
    if config.toxic_language:
        input_validators.append(LlmToxic(on_fail="exception"))

    if config.detect_pii_output:
        output_validators.append(DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"))
    if config.secrets_present_output:
        output_validators.append(SecretsPresent(on_fail="exception"))
    if config.is_safe_output:
        output_validators.append(IsSafeOutput(on_fail="exception"))

    input_guard = Guard().use(*input_validators) if input_validators else Guard()
    output_guard = Guard().use(*output_validators) if output_validators else Guard()

    print("[GUARDRAILS] Input validators order:")
    for v in input_validators:
        print(f"  - {v.__class__.__name__}")

    print("[GUARDRAILS] Output validators order:")
    for v in output_validators:
        print(f"  - {v.__class__.__name__}")

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
        llm_model, llm_callable = _build_global_gemini_llm_callable()
        print(f"[GUARDRAILS][INPUT] validate start msg_len={len(payload.message)}")

        # Provide llm callable to custom validators via metadata.
        outcome = input_guard.validate(
            payload.message,
            metadata={
                "llm_callable": llm_callable,
            },
        )
        print(f"[GUARDRAILS][INPUT] validate end passed={bool(outcome.validation_passed)}")

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
        print(f"[GUARDRAILS][INPUT][ERROR] validate failed: {type(e).__name__}: {e}")
        return ValidationResponse(is_safe=False, filtered_message=None, reason=_extract_reason(e))


@app.post("/check_output", response_model=ValidationResponse)
def check_output(payload: ValidationRequest) -> ValidationResponse:
    global output_guard
    if output_guard is None:
        return ValidationResponse(is_safe=False, filtered_message=None, reason="Guards not initialized.")

    try:
        llm_model, llm_callable = _build_global_gemini_llm_callable()
        print(f"[GUARDRAILS][OUTPUT] validate start msg_len={len(payload.message)}")

        # Provide llm callable to custom validators via metadata.
        outcome = output_guard.validate(
            payload.message,
            metadata={
                "llm_callable": llm_callable,
            },
        )
        print(f"[GUARDRAILS][OUTPUT] validate end passed={bool(outcome.validation_passed)}")
        return ValidationResponse(
            is_safe=bool(outcome.validation_passed),
            filtered_message=outcome.validated_output if outcome.validation_passed else None,
            reason=None,
        )
    except Exception as e:
        print(f"[GUARDRAILS][OUTPUT][ERROR] validate failed: {type(e).__name__}: {e}")
        return ValidationResponse(is_safe=False, filtered_message=None, reason=_extract_reason(e))


@app.get("/config", response_model=GuardrailsConfigResponse)
def get_config() -> GuardrailsConfigResponse:
    # use vars(config) if config.__dict__ fails. Or since it's an instance of a dataclass/simple object:
    return GuardrailsConfigResponse(
        is_safe_input=config.is_safe_input,
        enforce_anonymous_mode=config.enforce_anonymous_mode,
        block_financial_advisory=config.block_financial_advisory,
        escalation_trigger=config.escalation_trigger,
        restrict_to_topic=config.restrict_to_topic,
        detect_pii_input=config.detect_pii_input,
        secrets_present_input=config.secrets_present_input,
        toxic_language=config.toxic_language,
        detect_pii_output=config.detect_pii_output,
        secrets_present_output=config.secrets_present_output,
        is_safe_output=config.is_safe_output,
        valid_topics=config.valid_topics
    )


@app.post("/config", response_model=GuardrailsConfigResponse)
def update_config(payload: GuardrailsConfigRequest) -> GuardrailsConfigResponse:
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # Re-initialize guards with new configuration
    startup_event()

    return GuardrailsConfigResponse(
        is_safe_input=config.is_safe_input,
        enforce_anonymous_mode=config.enforce_anonymous_mode,
        block_financial_advisory=config.block_financial_advisory,
        escalation_trigger=config.escalation_trigger,
        restrict_to_topic=config.restrict_to_topic,
        detect_pii_input=config.detect_pii_input,
        secrets_present_input=config.secrets_present_input,
        toxic_language=config.toxic_language,
        detect_pii_output=config.detect_pii_output,
        secrets_present_output=config.secrets_present_output,
        is_safe_output=config.is_safe_output,
        valid_topics=config.valid_topics
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