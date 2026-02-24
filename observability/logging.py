"""
Centralized logging configuration with Loki exporter support.
"""
import logging
import sys
from typing import Optional
from logging.handlers import RotatingFileHandler

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from .model_configs import LoggingSettings


# Global logger provider
_logger_provider: Optional[LoggerProvider] = None


def setup_logging() -> logging.Logger:
    """
    Setup centralized logging with optional Loki/OTLP export.
    
    Returns:
        Configured root logger
    """
    global _logger_provider
    
    # Load settings
    settings = LoggingSettings()
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Set log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=settings.log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if settings.log_file:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # OTLP/Loki exporter (optional)
    if settings.enable_loki_export and settings.loki_endpoint:
        try:
            # Create resource with service information
            resource = Resource.create({
                SERVICE_NAME: settings.service_name or "unknown-service"
            })
            
            # Create logger provider
            _logger_provider = LoggerProvider(resource=resource)
            
            # Create OTLP log exporter
            otlp_exporter = OTLPLogExporter(
                endpoint=settings.loki_endpoint,
                insecure=True
            )
            
            # Add batch processor
            _logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(otlp_exporter)
            )
            
            # Set global logger provider
            set_logger_provider(_logger_provider)
            
            # Add OTLP handler to root logger
            otlp_handler = LoggingHandler(
                level=log_level,
                logger_provider=_logger_provider
            )
            root_logger.addHandler(otlp_handler)
            
            root_logger.info(
                f"Loki logging enabled: service={settings.service_name}, "
                f"endpoint={settings.loki_endpoint}"
            )
        except Exception as e:
            root_logger.warning(f"Failed to setup Loki logging: {e}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def shutdown_logging():
    """Shutdown logging and flush any pending log records."""
    global _logger_provider
    
    if _logger_provider:
        try:
            _logger_provider.shutdown()
        except Exception as e:
            logging.error(f"Error shutting down logger provider: {e}")
