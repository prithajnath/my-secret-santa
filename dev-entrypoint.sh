#!/usr/bin/env bash
./checkdb.sh

export FLASK_APP=app.py
flask db upgrade
python app.py