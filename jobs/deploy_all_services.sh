#!/usr/bin/env bash

docker-compose -f docker-compose-prod.yml pull
docker-compose -f docker-compose-prod.yml run -d