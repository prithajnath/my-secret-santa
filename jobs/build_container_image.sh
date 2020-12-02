#!/usr/bin/env bash

echo "$DOCKERHUB_PASS" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
docker-compose -f docker-compose-prod.yml build
docker-compose -f docker-compose-prod.yml push