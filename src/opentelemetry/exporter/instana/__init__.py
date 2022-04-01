# (c) Copyright IBM Corp. 2022 All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


"""
The **OpenTelemetry Instana Exporter** provides a span exporter from
`OpenTelemetry`_ traces to `Instana`_ .

Installation
------------

::

    pip install opentelemetry-exporter-instana


Usage
-----

The Instana exporter provides a span processor that must be added along with
the exporter.

.. code:: python

    from opentelemetry import trace
    from opentelemetry.exporter.instana import (
        InstanaExportSpanProcessor,
        InstanaSpanExporter,
    )
    from opentelemetry.sdk.trace import TracerProvider

    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    # Alternatively to passing the service_name, agent_key and endpoint_url explicitly
    # provide the agent key and backend endpoint URL environment variables:
    # * INSTANA_SERVICE_NAME
    # * INSTANA_AGENT_KEY
    # * INSTANA_ENDPOINT_URL
    exporter = InstanaSpanExporter(
        service_name="my-helloworld-service",
        agent_key="OAIqqcsUp4qai-Mukke5g",
        endpoint_url="https://serverless-blue-saas.instana.io",
    )

    span_processor = InstanaExportSpanProcessor(exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    with tracer.start_as_current_span("foo"):
        print("Hello world!")


Examples
--------

The `docs/examples/instana_exporter`_ includes examples for using the Instana
exporter with OpenTelemetry instrumented applications.

API
---
.. _Instana: https://www.ibm.com/docs/en/obi/current
.. _OpenTelemetry: https://github.com/open-telemetry/opentelemetry-python/
.. _docs/examples/instana_exporter:
      https://github.com/instana/opentelemetry-python-exporter-instana
             /tree/main/docs/examples/instana_exporter
"""

from .exporter import InstanaSpanExporter

# from .spanprocessor import InstanaExportSpanProcessor

__all__ = [
    "InstanaSpanExporter",
]  # "InstanaExportSpanProcessor", ]
