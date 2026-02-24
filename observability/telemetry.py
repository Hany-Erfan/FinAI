"""
OpenTelemetry telemetry setup for distributed tracing.
"""
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Try to import additional instrumentors
try:
    from opentelemetry.instrumentation.aiohttp import AioHTTPClientInstrumentor
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
    HAS_URLLIB3 = True
except ImportError:
    HAS_URLLIB3 = False

try:
    from opentelemetry.instrumentation.urllib import URLLibInstrumentor
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

from .model_configs import TelemetrySettings

logger = logging.getLogger(__name__)


def setup_telemetry() -> Optional[TracerProvider]:
    """
    Setup OpenTelemetry tracing with OTLP exporter and automatic instrumentation.
    """
    # Load settings from environment variables
    settings = TelemetrySettings()
    
    # Check if tracing is enabled
    if not settings.traces_enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return None
    
    # Validate required fields
    if not settings.service_name:
        logger.warning("Service name not configured. Set OTEL_SERVICE_NAME.")
        return None
    
    if not settings.exporter_otlp_endpoint:
        logger.warning("OTLP endpoint not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT.")
        return None
    
    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: settings.service_name,
        SERVICE_VERSION: settings.service_version,
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Create OTLP exporter based on protocol
    try:
        endpoint = settings.exporter_otlp_endpoint
        protocol_lower = settings.exporter_otlp_protocol.lower()
        
        if protocol_lower in ["grpc", "grpc/protobuf"]:
            exporter = GRPCExporter(endpoint=endpoint, insecure=True)
        elif protocol_lower in ["http", "http/protobuf"]:
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint}/v1/traces"
            exporter = HTTPExporter(endpoint=endpoint)
        else:
            logger.error(f"Unsupported protocol: {settings.exporter_otlp_protocol}")
            return None
        
        # Add span processor with batch export
        provider.add_span_processor(BatchSpanProcessor(exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        # Set global propagator for context propagation across services
        set_global_textmap(TraceContextTextMapPropagator())
        
        # Automatic instrumentation for HTTP clients
        HTTPXClientInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        
        # Additional HTTP client instrumentors
        if HAS_AIOHTTP:
            AioHTTPClientInstrumentor().instrument()
            logger.info("AioHTTP client instrumentation enabled")
        if HAS_URLLIB3:
            URLLib3Instrumentor().instrument()
            logger.info("URLLib3 instrumentation enabled")
        if HAS_URLLIB:
            URLLibInstrumentor().instrument()
            logger.info("URLLib instrumentation enabled")
        
        logger.info(
            f"OpenTelemetry initialized: service={settings.service_name}, "
            f"endpoint={settings.exporter_otlp_endpoint}, protocol={settings.exporter_otlp_protocol}"
        )
        
        # Enable logging instrumentation if requested
        if settings.enable_logging_instrumentation:
            LoggingInstrumentor().instrument(set_logging_format=True)
        
        return provider
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return None


def instrument_app(app):
    """
    Instrument a FastAPI or Starlette application for OpenTelemetry.
    
    Args:
        app: The application instance
    """
    settings = TelemetrySettings()
    if settings.traces_enabled:
        from fastapi import FastAPI
        from starlette.applications import Starlette
        
        if isinstance(app, FastAPI):
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI application instrumented for OpenTelemetry")
        elif isinstance(app, Starlette):
            StarletteInstrumentor().instrument_app(app)
            logger.info("Starlette application instrumented for OpenTelemetry")
        else:
            # Try generic instrumentation if it's neither but looks like an ASGI app
            try:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("Application instrumented for OpenTelemetry (generic)")
            except Exception as e:
                logger.warning(f"Failed to instrument application: {e}")


def get_tracer(name: str = __name__) -> trace.Tracer:
    """
    Get a tracer instance for the given name.
    """
    return trace.get_tracer(name)
