#!/usr/bin/env bash
python manage.py db migrate
python manage.py db upgrade

CONCURRENCY=$(expr 2 \* $(nproc) + 1)
gunicorn -w  $CONCURRENCY \
    --worker-class=gevent \
    --worker-connections=100 \
    --timeout 120 \
    --log-level=debug \
    --threads=$CONCURRENCY \
    --bind 0.0.0.0:$PORT \
    app:app

