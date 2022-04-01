from time import sleep

from celery import Celery

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

from pydantic import BaseModel

import requests

CELERY = Celery("tasks",
                backend="redis://192.168.1.199:6379",
                broker='redis://192.168.1.199:6379'
                # broker='pyamqp://guest@192.168.1.199/'
                )
CELERY.conf.task_default_queue = "trace_test-default"

app = FastAPI(
    title="API_3",
    description="lalalala",
    version="1.0.0",
    docs_url="/",
)

resource = Resource(attributes={"service.name": "trace_app3"})
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

@app.get("/", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI"
    )

class Obj_In(BaseModel):
    body: str

@app.post("/no_modification")
def trace_no_modification(obj_in: Obj_In):
    sleep(2)
    return JSONResponse({"Body": True})

@app.post("/modification")
def trace_modification(obj_in: Obj_In):
    sleep(2)
    return JSONResponse({"Body": True})

@app.post("/celery_bypass")
def trace_celery_bypass(obj_in: Obj_In):
    sleep(2)
    return JSONResponse({"Body": True})