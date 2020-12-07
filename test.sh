#!/usr/bin/env bash

echo "$(date) : spawning the secret santa container army"
cat << santatext

 /"       )/"     "| /" _  "\  /"      \  /"     "|("     _   ")     /"       )   /""\    (\"   \|"  \("     _   ") /""\     
(:   \___/(: ______)(: ( \___)|:        |(: ______) )__/  \\__/     (:   \___/   /    \   |.\\   \    |)__/  \\__/ /    \    
 \___  \   \/    |   \/ \     |_____/   ) \/    |      \\_ /         \___  \    /' /\  \  |: \.   \\  |   \\_ /   /' /\  \   
  __/  \\  // ___)_  //  \ _   //      /  // ___)_     |.  |          __/  \\  //  __'  \ |.  \    \. |   |.  |  //  __'  \  
 /" \   :)(:      "|(:   _) \ |:  __   \ (:      "|    \:  |         /" \   :)/   /  \\  \|    \    \ |   \:  | /   /  \\  \ 
(_______/  \_______) \_______)|__|  \___) \_______)     \__|        (_______/(___/    \___)\___|\____\)    \__|(___/    \___)

santatext

docker-compose up -d

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

# Build the Puppeteer image
docker build -t santa-puppet -f puppeteer.Dockerfile .

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

docker run --security-opt seccomp=chrome.json --network=my-secret-santa_santa_test_network santa-puppet

echo "$(date) cleaning up"
docker-compose rm -vfs
