"""
Guardrails Service
Analyzes inputs and outputs for the routing agent using Guardrails Hub validators (NO custom LLM calls).

Required hub installs (examples):
  guardrails hub install hub://guardrails/detect_pii
  guardrails hub install hub://guardrails/secrets_present
  guardrails hub install hub://guardrails/toxic_language
  guardrails hub install hub://guardrails/gibberish_text
  guardrails hub install hub://tryolabs/restricttotopic
"""

from __future__ import annotations

import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
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
    version="1.2.0",
)


class ValidationRequest(BaseModel):
    message: str


class ValidationResponse(BaseModel):
    is_safe: bool
    filtered_message: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------
# Custom Validators (rule-based, no LLMs)
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
# Hub Validator Configuration (less strict / more coverage)
# ---------------------------------------------------------

PII_ENTITIES = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "US_SSN"]

# Broader, more realistic banking topics/phrases so RestrictToTopic matches better
VALID_TOPICS = [
    # broad umbrella terms
    "banking",
    "retail banking",
    "customer support",
    "help",
    "account help",
    "online banking",
    "mobile banking",

    # auth/login
    "login",
    "sign in",
    "password",
    "password reset",
    "username",
    "locked account",
    "access",

    # general info
    "bank hours",
    "branch location",
    "atm",
    "routing number",
    "swift",
    "iban",
    "fees",

    # accounts & transfers (general)
    "bank account",
    "checking account",
    "savings account",
    "account balance",
    "transactions",
    "transaction history",
    "deposits",
    "direct deposit",
    "check deposit",
    "transfer",
    "wire transfer",
    "international transfer",
    "card",
    "debit card",
    "credit card",
    "dispute",
    "chargeback",

    # onboarding/products
    "open account",
    "opening an account",
    "onboarding",
    "sign up",
    "register",
    "apply",
    "loan",
    "mortgage",
]

input_guard: Optional[Guard] = None
output_guard: Optional[Guard] = None


@app.on_event("startup")
def startup_event() -> None:
    """
    Initialize guards once at startup.
    Uses ONLY Hub validators + simple rule-based custom validators.
    No LLM-based validator is used.
    """
    global input_guard, output_guard

    # INPUT:
    # - Keep rule-based checks
    # - Make RestrictToTopic more forgiving (lower threshold + broader topics)
    # - Keep PII detection
    # - Keep Toxic/Gibberish
    # - Make SecretsPresent non-blocking for INPUT (it is noisy for natural language)
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
                disable_llm=True,        # no LLM fallback
                model_threshold=0.35,    # less strict than 0.5
                on_fail="exception",
            ),

            DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"),

            # Don't hard-block on secrets for normal user messages
            SecretsPresent(on_fail="noop"),

            ToxicLanguage(threshold=0.6, validation_method="sentence", on_fail="exception"),
            GibberishText(threshold=0.6, validation_method="sentence", on_fail="exception"),
        )
    )

    # OUTPUT:
    # Keep strict (PII + secrets + toxicity/gibberish), because output is what you return to users.
    output_guard = (
        Guard()
        .use(
            DetectPII(pii_entities=PII_ENTITIES, on_fail="exception"),
            SecretsPresent(on_fail="exception"),
            ToxicLanguage(threshold=0.6, validation_method="sentence", on_fail="exception"),
            GibberishText(threshold=0.6, validation_method="sentence", on_fail="exception"),
            IsSafeOutput(on_fail="exception"),
        )
    )


def _extract_reason(exc: Exception) -> str:
    """
    Guardrails exceptions can be verbose; return a readable reason string.
    """
    msg = str(exc).strip()
    if not msg:
        return "Validation failed."
    return msg


@app.post("/check_input", response_model=ValidationResponse)
def check_input(payload: ValidationRequest) -> ValidationResponse:
    global input_guard
    if input_guard is None:
        return ValidationResponse(is_safe=False, filtered_message=None, reason="Guards not initialized.")

    try:
        outcome = input_guard.validate(payload.message)
        return ValidationResponse(
            is_safe=bool(outcome.validation_passed),
            filtered_message=outcome.validated_output if outcome.validation_passed else None,
            reason=None,
        )
    except Exception as e:
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


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    """Main entrypoint for Guardrails service server"""
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