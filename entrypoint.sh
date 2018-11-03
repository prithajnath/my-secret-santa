#!/usr/bin/env bash
python manage.py db migrate
python manage.py db upgrade
gunicorn --bind 0.0.0.0:$PORT app:app

