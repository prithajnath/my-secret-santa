#!/usr/bin/env bash

echo "$(date) : spawning the secret santa container army"
docker-compose up -d
sleep 10
echo "$(date) : running the secret santa test suite"
docker exec secret-santa-2018_secret-santa-web_1 pytest -vv

echo "$(date) cleaning up"

docker-compose rm -vfs
