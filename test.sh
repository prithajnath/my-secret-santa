#!/usr/bin/env bash

clean_up () {
    ARG=$?
    echo "$(date) cleaning up"
    docker image rm -f santa-puppet
    docker-compose rm -vfs
    exit $ARG
}
trap clean_up EXIT


echo "$(date) : spawning the secret santa container army"
cat << santatext

 /"       )/"     "| /" _  "\  /"      \  /"     "|("     _   ")     /"       )   /""\    (\"   \|"  \("     _   ") /""\
(:   \___/(: ______)(: ( \___)|:        |(: ______) )__/  \\__/     (:   \___/   /    \   |.\\   \    |)__/  \\__/ /    \
 \___  \   \/    |   \/ \     |_____/   ) \/    |      \\_ /         \___  \    /' /\  \  |: \.   \\  |   \\_ /   /' /\  \
  __/  \\  // ___)_  //  \ _   //      /  // ___)_     |.  |          __/  \\  //  __'  \ |.  \    \. |   |.  |  //  __'  \
 /" \   :)(:      "|(:   _) \ |:  __   \ (:      "|    \:  |         /" \   :)/   /  \\  \|    \    \ |   \:  | /   /  \\  \
(_______/  \_______) \_______)|__|  \___) \_______)     \__|        (_______/(___/    \___)\___|\____\)    \__|(___/    \___)

santatext

docker-compose up --build -d

while [ $(docker ps | grep dev-secret-santa | wc -l ) -ne "4" ]; do
    sleep 5
done

container_name=dev-secret-santa-web

# Check if database has been initialized yet (Relations MUST exist)
echo "$(date) : checking database readiness"
while true; do
db=$(docker exec $container_name psql -h secret-santa-postgres -U postgres --db postgres -c "\\d")
    [ $? -eq 0 ] && [[ $db =~ "users" ]] && echo $db && break
    sleep 5
done

echo "$(date) : running the secret santa test suite"
docker exec $container_name pytest -vv

# Insert user helenkeller into the db
pass=\$pbkdf2-sha256\$29000\$xFiLUeq9N2YMgVBKqdXaOw\$kcnjB2FPGFk/cr0Yhyw7T4bcCWNaW/NqF8xa1Ktf1OA

read -r -d '' SQL << sql
INSERT INTO
  USERS(
      username,
      password,
      email,
      first_name,
      last_name,
      hint,
      address
) VALUES ('helenkeller', '$pass', 'helenk55@mysecretsanta.io', 'Helen', 'Keller', 'somehint', 'whereilive');
sql

echo "$SQL"

docker exec $container_name psql -h secret-santa-postgres -U postgres --db postgres -c "$SQL"

# Check disk space available before building the puppeteer image. Blow up if low on disk space
read -r -d '' PYTHON << py
import shutil
import sys

PUPPETEER_IMAGE_SIZE=2.3

_, _, free = shutil.disk_usage("/")
enough_disk_space = free / (2**30)
print(f"{enough_disk_space:.2f} GB disk space available")
if enough_disk_space - PUPPETEER_IMAGE_SIZE < 1:
    sys.exit(1)
py

python3 -c "$PYTHON"

# Build the Puppeteer image
docker build -t santa-puppet -f puppeteer.Dockerfile .

docker run --security-opt seccomp=chrome.json --network=my-secret-santa_santa_test_network santa-puppet
