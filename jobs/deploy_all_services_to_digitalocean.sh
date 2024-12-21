#!/usr/bin/env bash

set -euo pipefail

docker compose -f docker-compose-prod-do.yml pull
docker compose -f docker-compose-prod-do.yml down
docker compose -f docker-compose-prod-do.yml up -d