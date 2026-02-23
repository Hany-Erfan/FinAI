"""
Guardrails Service
Analyzes inputs and outputs for the routing agent using GuardrailAI logic.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os

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


@app.post("/check_input", response_model=ValidationResponse)
async def check_input(payload: ValidationRequest):
    """
    Validates user input *before* it gets sent to the agent.
    Implement actual guardrails-ai logic here.
    """
    # TODO: Add real guardrails-ai logic here. For now, basic mock validation.
    is_safe = True
    reason = None
    
    # Example basic guard:
    dangerous_keywords = ["drop table", "ignore previous instructions", "bypass"]
    if any(keyword in payload.message.lower() for keyword in dangerous_keywords):
        is_safe = False
        reason = "Potentially malicious input detected."

    return ValidationResponse(
        is_safe=is_safe,
        filtered_message=payload.message if is_safe else None,
        reason=reason
    )

@app.post("/check_output", response_model=ValidationResponse)
async def check_output(payload: ValidationRequest):
    """
    Validates agent output *before* returning it to the user.
    Implement actual guardrails-ai logic here.
    """
    # TODO: Add real guardrails-ai logic here. For now, basic mock validation.
    is_safe = True
    reason = None
    
    # Example basic guard:
    if "credit card number" in payload.message.lower():
        is_safe = False
        reason = "Sensitive PII detected in output."

    return ValidationResponse(
        is_safe=is_safe,
        filtered_message=payload.message if is_safe else None,
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
