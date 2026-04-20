from setuptools import setup, find_packages

setup(
    name="observability",
    version="1.0.0",
    description="OpenTelemetry observability module for FinAI agents",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.10.0",
        "pydantic-settings>=2.7.0",
        "opentelemetry-api>=1.29.0",
        "opentelemetry-sdk>=1.29.0",
        "opentelemetry-exporter-otlp-proto-grpc>=1.29.0",
        "opentelemetry-exporter-otlp-proto-http>=1.29.0",
        "opentelemetry-instrumentation-fastapi>=0.50b0",
        "opentelemetry-instrumentation-requests>=0.50b0",
        "opentelemetry-instrumentation-httpx>=0.50b0",
        "opentelemetry-instrumentation-logging>=0.50b0",
        "opentelemetry-instrumentation-starlette>=0.50b0",
    ],
    python_requires=">=3.11",
)
