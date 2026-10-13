from contextlib import contextmanager
from dataclasses import asdict
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor,BatchSpanProcessor,SpanExporter,SpanExportResult
from opentelemetry.trace import Status,StatusCode,get_current_span
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from researchflow.infrastructure.telemetry.redaction import redact


class ResilientExporter(SpanExporter):
    def __init__(self,delegate):
        self.delegate=delegate
    def export(self,spans):
        try:
            return self.delegate.export(spans)
        except Exception:
            return SpanExportResult.FAILURE
    def shutdown(self):
        try:
            self.delegate.shutdown()
        except Exception:
            pass


class SafeSpan:
    def __init__(self,span):
        self.span=span
    def set_attribute(self,key,value):
        for k,v in redact({key:value}).items():
            self.span.set_attribute(k,v)
    def add_event(self,name,attributes=None):
        self.span.add_event(name,redact(attributes or {}))


class OpenTelemetryTrace:
    def __init__(self,exporter=None,endpoint=None):
        self.provider=TracerProvider(sampler=ALWAYS_ON if exporter is not None else None,shutdown_on_exit=False)
        if exporter is not None:
            self.provider.add_span_processor(SimpleSpanProcessor(ResilientExporter(exporter)))
        elif endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            self.provider.add_span_processor(BatchSpanProcessor(ResilientExporter(OTLPSpanExporter(endpoint=endpoint))))
        self.tracer=self.provider.get_tracer('researchflow','1.0.0')

    @contextmanager
    def span(self,name,attributes):
        with self.tracer.start_as_current_span(name,attributes=redact(attributes),record_exception=False,set_status_on_exception=False) as span:
            try:
                yield SafeSpan(span)
            except BaseException:
                span.set_status(Status(StatusCode.ERROR))
                raise

    def record_failure(self,failure):
        get_current_span().add_event('failure',redact(asdict(failure)))

    def close(self):
        self.provider.shutdown()
