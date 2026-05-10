import logging
from contextlib import contextmanager

import config

logger = logging.getLogger(__name__)
_initialized = False
_tracer = None


def init_observability(service_name: str = None):
    global _initialized, _tracer
    if _initialized:
        return _tracer
    _initialized = True

    if not config.OTEL_ENABLED:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({"service.name": service_name or config.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        if config.OTEL_EXPORTER_OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT))
            )

        if config.OTEL_CONSOLE_EXPORT or not config.OTEL_EXPORTER_OTLP_ENDPOINT:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name or config.OTEL_SERVICE_NAME)
        return _tracer
    except Exception as exc:
        logger.warning("OpenTelemetry initialization skipped: %s", exc)
        return None


def get_tracer():
    return _tracer or init_observability()


@contextmanager
def start_span(name: str, attributes: dict = None):
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_attribute("error", True)
            raise


def instrument_fastapi_app(app, service_name: str = None):
    init_observability(service_name)
    if not config.OTEL_ENABLED:
        return app

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("FastAPI OpenTelemetry instrumentation skipped: %s", exc)
    return app


class Observability:
    """Compatibility wrapper used by the existing RAGSystem."""

    def __init__(self, service_name: str = None):
        self.tracer = init_observability(service_name)

    def get_handler(self):
        return None

    def start_span(self, name: str, attributes: dict = None):
        return start_span(name, attributes)

    def flush(self):
        try:
            from opentelemetry import trace

            provider = trace.get_tracer_provider()
            force_flush = getattr(provider, "force_flush", None)
            if callable(force_flush):
                force_flush()
        except Exception:
            pass
