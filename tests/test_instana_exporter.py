# (c) Copyright IBM Corp. 2022 All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import unittest
from types import SimpleNamespace

from unittest.mock import NonCallableMock

from instana.recorder import StanRecorder

from opentelemetry import trace as trace_api
from opentelemetry.exporter import instana as instana_exporter
from opentelemetry.sdk import trace
from opentelemetry.sdk.trace import Resource
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.util.instrumentation import InstrumentationInfo


class TestInstanaSpanExporter(unittest.TestCase):
    def setUp(self):
        self.span_queue = NonCallableMock()
        self.mock_collector = NonCallableMock(span_queue=self.span_queue)
        self.mock_collector.queued_spans.return_value = []
        mock_agent = NonCallableMock()
        mock_agent.collector = self.mock_collector
        self.recorder = StanRecorder(agent=mock_agent)

        self.exporter = instana_exporter.InstanaSpanExporter(agent=mock_agent)

    def test_export(self):
        """Test that agent and/or collector are invoked"""
        context = trace_api.SpanContext(
            trace_id=0x000000000000000000000000DEADBEEF,
            span_id=0x00000000DEADBEF0,
            is_remote=False,
        )

        span_name = "test_span"
        # Use `_Span` because `Span` can only be instantiated
        # by a tracer
        test_span = trace._Span(span_name, context=context)
        test_span.start()
        test_span.end()

        result = self.exporter.export((test_span,))

        self.assertEqual(result, SpanExportResult.SUCCESS)

        # Ensure that the exported span has been actually put into the span queue
        # before reporting the export result a success
        self.span_queue.put.assert_called_once()

        # Ensure that the emptyness of the span queue has been checked
        # before reporting the export result a success
        # that is normally the side-effect of having everything sent
        self.mock_collector.queued_spans.assert_called_once()

        # instana_span = self.span_queue.mock_calls[0].args[0]
        # This above would only work Python >= 3.8:
        # https://bugs.python.org/issue21269
        # So in order to support 3.7 we need this ugly hack:
        instana_span = tuple(self.span_queue.mock_calls[0])[1][0]

        # Ensure that the 'n' attribute in the instana span
        # is the same as the 'name' of the otel span
        self.assertEqual(instana_span.n, span_name)

    # pylint: disable=too-many-locals
    def test_translate_to_instana(self):
        """Test the translation of spans in OTLP format to instana format"""

        resource = Resource(
            attributes={
                "key_resource": "some_resource",
                "service.name": "resource_service_name",
            }
        )

        resource_without_service = Resource(
            attributes={"conflicting_key": "conflicting_value"}
        )

        span_names = ("test1", "test2", "test3")
        trace_id = 0x6E0C63257DE34C926F9EFCD03927272E
        trace_id_low = 0x6F9EFCD03927272E
        span_id = 0x34BF92DEEFC58C92
        parent_id = 0x1111111111111111
        other_id = 0x2222222222222222

        base_time = 683647322 * 10**9  # in ns
        start_times = (
            base_time,
            base_time + 150 * 10**6,
            base_time + 300 * 10**6,
        )
        durations = (50 * 10**6, 100 * 10**6, 200 * 10**6)
        end_times = (
            start_times[0] + durations[0],
            start_times[1] + durations[1],
            start_times[2] + durations[2],
        )

        span_context = trace_api.SpanContext(trace_id, span_id, is_remote=False)
        parent_span_context = trace_api.SpanContext(
            trace_id, parent_id, is_remote=False
        )
        other_context = trace_api.SpanContext(trace_id, other_id, is_remote=False)

        instrumentation_info = InstrumentationInfo(__name__, "0")

        pid = str(os.getpid())
        otel_spans = [
            trace._Span(
                name=span_names[0],
                context=span_context,
                parent=parent_span_context,
                kind=trace_api.SpanKind.CLIENT,
                instrumentation_info=instrumentation_info,
                resource=Resource({}),
            ),
            trace._Span(
                name=span_names[1],
                context=parent_span_context,
                parent=None,
                instrumentation_info=instrumentation_info,
                resource=resource_without_service,
            ),
            trace._Span(
                name=span_names[2],
                context=other_context,
                parent=None,
                resource=resource,
            ),
        ]

        otel_spans[1].set_attribute("conflicting_key", "original_value")

        otel_spans[0].start(start_time=start_times[0])
        otel_spans[0].end(end_time=end_times[0])

        otel_spans[1].start(start_time=start_times[1])
        otel_spans[1].end(end_time=end_times[1])

        otel_spans[2].start(start_time=start_times[2])
        otel_spans[2].end(end_time=end_times[2])

        instana_spans = self.exporter._translate_to_instana(otel_spans)

        expected_spans = [
            SimpleNamespace(
                t=str(trace_id_low),
                lt=str(trace_id),
                p=str(parent_id),
                s=str(span_id),
                k="client",
                n=span_names[0],
                ts=start_times[0],
                d=durations[0],
                ec=0,
                data={},
                f={"e": pid},
            ),
            SimpleNamespace(
                t=str(trace_id_low),
                lt=str(trace_id),
                s=str(parent_id),
                k="internal",
                n=span_names[1],
                ts=start_times[1],
                d=durations[1],
                ec=0,
                data={
                    "tags": {
                        "conflicting_key": "original_value",
                    },
                },
                f={"e": pid},
            ),
            SimpleNamespace(
                t=str(trace_id_low),
                lt=str(trace_id),
                s=str(other_id),
                k="internal",
                n=span_names[2],
                ts=start_times[2],
                d=durations[2],
                ec=0,
                data={},
                service="resource_service_name",
                f={"e": pid},
            ),
        ]

        for instana_span, expected_span in zip(instana_spans, expected_spans):
            self.assertEqual(instana_span, expected_span)
