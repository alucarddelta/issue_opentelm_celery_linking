Issue with Opentelemetry celery

Tasks are not linking back to the requested task out side of the same worker.

Set up with a local instance of redis

app1 setup:
uvicorn app1.main:app --reload --host 0.0.0.0 --port 5001

app2 setup:
celery -A app2.main worker --loglevel=INFO --pool=prefork --concurrency=1 -n trace_test2@%h --task-events

app3 setup:
uvicorn app3.main:app --reload --host 0.0.0.0 --port 5003

app4 setup:
celery -A app4.main worker --loglevel=INFO --pool=prefork --concurrency=1 -n trace_test4@%h --task-events