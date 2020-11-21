#!/usr/bin/env bash
celery -A tasks.celery worker --uid=$UID --loglevel=INFO --concurrency=$(expr 2 \* $(nproc) + 1) -n worker1@%h