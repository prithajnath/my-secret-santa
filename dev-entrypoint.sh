#!/usr/bin/env bash
./checkdb.sh

export FLASK_APP=app.py
flask db migrate
flask db upgrade
python app.py