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

while [ $(docker ps | grep secret-santa | wc -l ) -ne "4" ]; do
    sleep 5
done

container_id=$(docker ps | grep web_1 | awk '{ print $1 }')

# Check if database has been initialized yet (Relations MUST exist)
echo "$(date) : checking database readiness"
while true; do
    db=$(docker exec $container_id psql -h secret-santa-postgres -U postgres --db postgres -c "\\d")
    [ $? -eq 0 ] && [[ $db =~ "users" ]] && echo $db && break
    sleep 5
done

echo "$(date) : running the secret santa test suite"
docker exec $container_id pytest -vv

echo "$(date) cleaning up"
docker-compose rm -vfs
