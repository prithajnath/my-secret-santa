#!/usr/bin/env bash
python manage.py db migrate
python manage.py db upgrade
gunicorn -w $(expr 2 \* $(nproc) + 1) \
    --timeout 120 \
    --bind 0.0.0.0:$PORT \
    app:app

