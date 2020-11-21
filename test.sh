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
sleep 10
echo "$(date) : running the secret santa test suite"
docker exec secret-santa-2018_secret-santa-web_1 pytest -vv

echo "$(date) cleaning up"

docker-compose rm -vfs
