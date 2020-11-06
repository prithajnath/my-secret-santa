#!/usr/bin/env bash
./checkdb.sh

python manage.py db migrate
python manage.py db upgrade
python app.py