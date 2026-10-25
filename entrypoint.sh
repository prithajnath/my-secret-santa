#!/usr/bin/env bash
export FLASK_APP=app.py
flask db upgrade

CONCURRENCY=$(expr 2 \* $(nproc) + 1)
gunicorn -w  $CONCURRENCY \
    --worker-class=gevent \
    --worker-connections=100 \
    --timeout 120 \
    --log-level=debug \
    --threads=$CONCURRENCY \
    --bind 0.0.0.0:$PORT \
    app:app

