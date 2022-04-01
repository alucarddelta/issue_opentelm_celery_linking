from time import sleep
from typing import Any, Union
import uuid
from celery import Celery, Task
from celery.signals import worker_process_init

from opentelemetry import trace, context
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

import requests

from pydantic import BaseModel

CELERY = Celery("tasks",
                backend="redis://192.168.1.199:6379",
                broker='redis://192.168.1.199:6379'
                # broker='pyamqp://guest@192.168.1.199/'
                )
CELERY.conf.task_default_queue = "trace_test-default"

CELERY_2 = Celery("tasks",
                backend="redis://192.168.1.199:6379",
                broker='redis://192.168.1.199:6379'
                # broker='pyamqp://guest@192.168.1.199/'
                )
CELERY_2.conf.task_default_queue = "trace_test_2-default"

tracer = trace.get_tracer(__name__)

@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    resource = Resource(attributes={"service.name": "trace_app2"})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    # Configure the tracer to export traces to Jaeger
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
CeleryInstrumentor().instrument()

RequestsInstrumentor().instrument()

class Obj_In(BaseModel):
    body: str

class CTX(BaseModel):
    trace_id: Any
    span_id: Any
    is_remote: bool
    trace_flags = TraceFlags(0x01)

@CELERY.task(name="no_modification", bind=True, track_started=True)
def trace_no_modification(self: Task, obj_in: Obj_In, **kwargs) -> Union[dict, str]:
    request = requests.post("http://localhost:5003/no_modification", json=obj_in)
    sleep(2)
    return request.json()

@CELERY.task(name="modification", bind=True, track_started=True)
def trace_modification(self: Task, obj_in: Obj_In, tracer_context: CTX, **kwargs) -> Union[dict, str]:
    ctx = trace.set_span_in_context(NonRecordingSpan(SpanContext(
        trace_id=tracer_context['trace_id'],
        span_id=tracer_context['span_id'],
        is_remote=False,
        trace_flags=TraceFlags(0x01) )))

    context.attach(ctx)

    request = requests.post("http://localhost:5003/modification", json=obj_in)
    sleep(2)
    return request.json()

@CELERY.task(name="celery_loop_start", bind=True, track_started=True)
def trace_celery_loop_start(self: Task, **kwargs) -> Union[dict, str]:
    generate_uuid = str(uuid.uuid4())
    task = CELERY.send_task(name="celery_loop_end", task_id=generate_uuid, args=[])
    task_id = task.id
    sleep(1)
    return

@CELERY.task(name="celery_loop_start_mod", bind=True, track_started=True)
def trace_celery_loop_start(self: Task, tracer_context: CTX, **kwargs) -> Union[dict, str]:
    ctx = trace.set_span_in_context(NonRecordingSpan(SpanContext(
        trace_id=tracer_context['trace_id'],
        span_id=tracer_context['span_id'],
        is_remote=False,
        trace_flags=TraceFlags(0x01) )))

    context.attach(ctx)

    task = CELERY.send_task(name="celery_loop_end", args=[])
    task_id = task.id
    sleep(1)
    return

@CELERY.task(name="celery_loop_end", bind=True, track_started=True)
def trace_celery_loop_end(self: Task, **kwargs) -> Union[dict, str]:
    print("Done")
    sleep(2)
    return

@CELERY.task(name="external_clery", bind=True, track_started=True)
def trace_external_clery(self: Task, obj_in: Obj_In, **kwargs) -> Union[dict, str]:
    generate_uuid = str(uuid.uuid4())
    task = CELERY_2.send_task(name="external_no_modification", task_id=generate_uuid, args=[obj_in])
    task_id = task.id
    sleep(1)
    return

@CELERY.task(name="external_clery_mod", bind=True, track_started=True)
def trace_external_clery_mod(self: Task, obj_in: Obj_In, tracer_context: CTX, **kwargs) -> Union[dict, str]:
    ctx = trace.set_span_in_context(NonRecordingSpan(SpanContext(
        trace_id=tracer_context['trace_id'],
        span_id=tracer_context['span_id'],
        is_remote=False,
        trace_flags=TraceFlags(0x01) )))

    context.attach(ctx)

    task = CELERY_2.send_task(name="external_modification", args=[obj_in, tracer_context])
    task_id = task.id
    sleep(1)
    return