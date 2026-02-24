"""
Guardrails Service
Analyzes inputs and outputs for the routing agent using GuardrailAI logic.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

from guardrails import Guard
from guardrails.validators import Validator, register_validator, ValidationResult, PassResult, FailResult

app = FastAPI(
    title="Guardrails Service",
    description="Validation service for routing agent inputs and outputs.",
    version="1.0.0",
)

class ValidationRequest(BaseModel):
    message: str

class ValidationResponse(BaseModel):
    is_safe: bool
    filtered_message: str | None = None
    reason: str | None = None

# ---------------------------------------------------------
# Define Custom Guardrails Validators
# ---------------------------------------------------------

@register_validator(name="is-safe-input", data_type="string")
class IsSafeInput(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        dangerous_keywords = ["drop table", "ignore previous instructions", "bypass"]
        if any(keyword in value.lower() for keyword in dangerous_keywords):
            return FailResult(error_message="Potentially malicious input detected.")
        return PassResult()

@register_validator(name="is-safe-output", data_type="string")
class IsSafeOutput(Validator):
    def validate(self, value: str, metadata: dict = {}) -> ValidationResult:
        if "credit card number" in value.lower():
            return FailResult(error_message="Sensitive PII detected in output.")
        return PassResult()

# ---------------------------------------------------------
# Initialize Guards
# ---------------------------------------------------------

input_guard = Guard().use(IsSafeInput, on_fail="exception")
output_guard = Guard().use(IsSafeOutput, on_fail="exception")


@app.post("/check_input", response_model=ValidationResponse)
async def check_input(payload: ValidationRequest):
    """
    Validates user input *before* it gets sent to the agent.
    Uses guardrails-ai to process validation.
    """
    is_safe = True
    reason = None
    filtered_message = payload.message

    try:
        # Validate the input using our Guard
        outcome = input_guard.validate(payload.message)
        if outcome.validation_passed:
            filtered_message = outcome.validated_output
        else:
            is_safe = False
            reason = "Validation failed."
    except Exception as e:
        is_safe = False
        reason = str(e)
        filtered_message = None

    return ValidationResponse(
        is_safe=is_safe,
        filtered_message=filtered_message if is_safe else None,
        reason=reason
    )

@app.post("/check_output", response_model=ValidationResponse)
async def check_output(payload: ValidationRequest):
    """
    Validates agent output *before* returning it to the user.
    Uses guardrails-ai to process validation.
    """
    is_safe = True
    reason = None
    filtered_message = payload.message

    try:
        # Validate the output using our Guard
        outcome = output_guard.validate(payload.message)
        if outcome.validation_passed:
            filtered_message = outcome.validated_output
        else:
            is_safe = False
            reason = "Validation failed."
    except Exception as e:
        is_safe = False
        reason = str(e)
        filtered_message = None

    return ValidationResponse(
        is_safe=is_safe,
        filtered_message=filtered_message if is_safe else None,
        reason=reason
    )

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
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
