# (c) Copyright IBM Corp. 2022

import logging
import os
import time
from types import SimpleNamespace

# from opentelemetry.sdk.trace import sampling
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind

from instana.singletons import get_agent  # , span_recorder, tracer

logger = logging.getLogger(__name__)


class InstanaSpanExporter(SpanExporter):
    """Instana span exporter for OpenTelemetry.

    Args:
        service_name:
            The custom service name to be used for the application
            or use the ``INSTANA_SERVICE_NAME`` environment variable
        agent_key:
            The Instana agent key or use ``INSTANA_AGENT_KEY`` environment variable
        endpoint_url:
            Endpoints for serverless monitoring
            or use the ``INSTANA_ENDPOINT_URL`` environment variable
    """

    def __init__(
        self, service_name=None, agent_key=None, endpoint_url=None, agent=None
    ):
        # instana.collector.helpers.runtime.RuntimeHelper would pick these up
        # from the environment directly
        if service_name:
            os.environ["INSTANA_SERVICE_NAME"] = service_name
        if agent_key:
            os.environ["INSTANA_AGENT_KEY"] = agent_key
        if agent_key:
            os.environ["INSTANA_ENDPOINT_URL"] = endpoint_url

        self.agent = agent or get_agent()
        # FSM should first announce and call start() on the agent,
        # which will call start on the collector
        # The FSM takes a ref to the Agent in the Agent's constructor
        self.collector = self.agent.collector

    def export(self, spans):
        # Start translation while the FSM is getting ready to send
        # in the background
        instana_spans = self._translate_to_instana(spans)

        for span in instana_spans:
            self.agent.collector.span_queue.put(span)

        # At this point we have to wait until the span_queue
        # has been sent out successfully
        while self.agent.collector.queued_spans():
            logger.warning("Queued spans have not been sent yet")
            time.sleep(5)

        logger.info("Successfully exported spans")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.collector.shutdown()

    # pylint: disable=no-self-use
    def _translate_to_instana(self, spans):
        def build_instana_trace_or_span_id(otel_id, flag):
            # TODO test this thoroughly
            instana_id = otel_id & 0xFFFFFFFFFFFFFFFF
            return str(instana_id)

        def translate(span):
            trace_id = build_instana_trace_or_span_id(span.context.trace_id, True)
            span_id = build_instana_trace_or_span_id(span.context.span_id, True)
            data_service = span.resource.attributes.get("service.name", None)

            result = {
                "n": span.name or "otel",
                "f": {
                    # On serverless this should not be the pid!
                    "e": str(os.getpid())
                },
                "k": span.kind.name.lower(),
                "data": {},
                "t": trace_id,
                "s": span_id,
                "ts": span.start_time,
                "d": span.end_time - span.start_time,
            }

            if span.context.trace_id > 0xFFFFFFFFFFFFFFFF:
                result["lt"] = str(span.context.trace_id)

            if span.parent:
                result["p"] = build_instana_trace_or_span_id(span.parent.span_id, True)
                # In case of an entry span kind, mark span as TraceParent
                if span.kind in (SpanKind.SERVER, SpanKind.CONSUMER):
                    result["tp"] = True

            if data_service:
                result["service"] = data_service

            if span.attributes:
                result["data"]["tags"] = dict(span.attributes.items())

            if span.events:
                # TODO test this with real events
                result["data"]["events"] = [*span.events]

            if span.status.is_ok:
                result["ec"] = 0
            else:
                result["ec"] = 1
                result["data"]["error"] = "ERROR"
                result["data"]["error_detail"] = span.status.description

            return SimpleNamespace(**result)

        instana_spans = [translate(span) for span in spans]

        return instana_spans
