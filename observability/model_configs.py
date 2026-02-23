"""
Pydantic models and configuration classes for observability.
"""
from typing import Optional, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelemetrySettings(BaseSettings):
    """
    OpenTelemetry configuration settings.
    
    All settings can be configured via environment variables with the OTEL_ prefix.
    """
    
    service_name: Optional[str] = Field(
        default=None,
        description="Name of the service for tracing"
    )
    
    service_version: str = Field(
        default="1.0.0",
        description="Version of the service"
    )
    
    exporter_otlp_endpoint: Optional[str] = Field(
        default=None,
        description="OTLP collector endpoint (e.g., http://localhost:4317)"
    )
    
    exporter_otlp_protocol: Literal["grpc", "http", "http/protobuf", "grpc/protobuf"] = Field(
        default="grpc",
        description="Protocol to use for OTLP export (grpc or http)"
    )
    
    traces_enabled: bool = Field(
        default=True,
        description="Enable or disable tracing"
    )
    
    enable_logging_instrumentation: bool = Field(
        default=True,
        description="Enable automatic logging instrumentation"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="OTEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class LoggingSettings(BaseSettings):
    """
    Centralized logging configuration settings.
    
    All settings can be configured via environment variables with the LOG_ prefix.
    """
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    
    log_file: Optional[str] = Field(
        default=None,
        description="Path to log file (optional, logs to console if not set)"
    )
    
    enable_loki_export: bool = Field(
        default=True,
        description="Enable export of logs to Loki via OTLP"
    )
    
    loki_endpoint: Optional[str] = Field(
        default=None,
        description="Loki OTLP endpoint (e.g., http://lgtm:4317)"
    )
    
    service_name: Optional[str] = Field(
        default=None,
        description="Service name for log attribution"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
