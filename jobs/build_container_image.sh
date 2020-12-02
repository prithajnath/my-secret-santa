#!/usr/bin/env bash

set -euo pipefail

echo "$DOCKERHUB_PASS" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin
docker-compose -f docker-compose-prod.yml build
docker-compose -f docker-compose-prod.yml push