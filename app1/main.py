from time import sleep
from typing import Any

from celery import Celery

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

import requests


CELERY = Celery("tasks",
                backend="redis://192.168.1.199:6379",
                broker='redis://192.168.1.199:6379'
                # broker='pyamqp://guest@192.168.1.199/'
                )
CELERY.conf.task_default_queue = "trace_test-default"

app = FastAPI(
    title="API_1",
    description="""
    app1 - Fastapi
    app2 - Celery
    app3 - Fastapi
    app4 - Celery
    """,
    version="1.0.0",
    docs_url="/",
)

resource = Resource(attributes={"service.name": "trace_app1"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# Configure the tracer to export traces to Jaeger
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

RequestsInstrumentor().instrument()
FastAPIInstrumentor.instrument_app(app)
CeleryInstrumentor().instrument()

@app.get("/", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI"
    )

class Obj_In(BaseModel):
    body: str

class CTX(BaseModel):
    trace_id: Any
    span_id: Any
    is_remote: bool

@app.post("/test1_a")
def post_standard(obj_in: Obj_In):
    """Send request with no modifications. As expected.

    app1 -> app2 -> app3

    Issue: app2 does not link back to app1 trace.
    """
    task = CELERY.send_task(name="no_modification", args=[obj_in.dict()])
    task_id = task.id
    sleep(1)
    return JSONResponse({"task_id": task_id})

@app.post("/test1_b")
def post_standard_modification(obj_in: Obj_In):
    """Send request with modifications to manually apply the context.

    app1 -> app2 -> app3

    Issue: app2 celery instrument span does not link to the new span created within the function.
    """
    with tracer.start_as_current_span("app1_test2_modification") as span:
        tracer_context = span.get_span_context()
        tracer_context_obj = CTX(trace_id= tracer_context.trace_id, span_id= tracer_context.span_id, is_remote=True)
        task = CELERY.send_task(name="modification", args=[obj_in.dict(), tracer_context_obj.dict()])
        task_id = task.id
        sleep(1)
        return JSONResponse({"task_id": task_id})

@app.post("/test2")
def post_fastapi_to_fastapi(obj_in: Obj_In):
    """Fast API to Fast API Skipping the Celery application.

    app1 -> app3

    Issue: None
    """
    request = requests.post("http://localhost:5003/celery_bypass", json=obj_in.dict())
    sleep(1)
    return request.json()

@app.post("/test3_a")
def post_internal_celery_link(obj_in: Obj_In):
    """Celery call to initiate another celery job within the same worker.

    app1 -> app2 -> app2

    Issue: Issue app2 trace does not link back to app2 trace

    Note: Celery Task that is created inside the 1st task is correctly linked.
    """
    task = CELERY.send_task(name="celery_loop_start", args=[])
    task_id = task.id
    sleep(1)
    return JSONResponse({"task_id": task_id})

@app.post("/test3_b")
def post_internal_celery_link_modification(obj_in: Obj_In):
    """Celery call to initiate another celery job within the same worker. manually apply the context to link the requests together.

    app1 -> app2 -> app2

    Issue: app2 celery instrument span does not link to the new span created within the function.

    Note: Celery Task that is created inside the 1st task is correctly linked.
    """
    with tracer.start_as_current_span("app1_celery_loop_start_mod") as span:
        tracer_context = span.get_span_context()
        tracer_context_obj = CTX(trace_id= tracer_context.trace_id, span_id= tracer_context.span_id, is_remote=True)
        task = CELERY.send_task(name="celery_loop_start_mod", args=[tracer_context_obj.dict()])
        task_id = task.id
        sleep(1)
        return JSONResponse({"task_id": task_id})

@app.post("/test4_a")
def post_external_celery(obj_in: Obj_In):
    """Celery call to initiate another celery job within the external worker.

    app1 -> app2 -> app4 -> app3

    Issue1: app2 does not link back to app1 trace.

    Issue2: app4 does not link back to app2 trace.
    """
    task = CELERY.send_task(name="external_clery", args=[obj_in.dict()])
    task_id = task.id
    sleep(1)
    return JSONResponse({"task_id": task_id})

@app.post("/test4_b")
def post_external_celery_modification(obj_in: Obj_In):
    """Celery call to initiate another celery job within the external worker. manually apply the context to link the requests together.

    app1 -> app2 -> app4 -> app3

    Issue1: app2 celery instrument span does not link to the new span created within the function.
    
    Issue2: app4 does not link back to app2 trace.
    """
    with tracer.start_as_current_span("app1_celery_external_modification") as span:
        tracer_context = span.get_span_context()
        tracer_context_obj = CTX(trace_id= tracer_context.trace_id, span_id= tracer_context.span_id, is_remote=True)
        task = CELERY.send_task(name="external_clery_mod", args=[obj_in.dict(), tracer_context_obj.dict()])
        task_id = task.id
        sleep(1)
        return JSONResponse({"task_id": task_id})

@app.get("/{task_id}")
def get_task(task_id: str) -> JSONResponse:
    """"""
    with tracer.start_as_current_span("app1_task_result"):
        task_result = CELERY.AsyncResult(task_id)
        result = {
            "task_id": task_result.id,
            "task_status": task_result.status,
            "task_result": str(task_result.result)
            if any([task_result.status == "FAILURE", task_result.status == "RETRY", task_result.status == "REVOKED"])
            else task_result.result,
        }
        return JSONResponse(result)