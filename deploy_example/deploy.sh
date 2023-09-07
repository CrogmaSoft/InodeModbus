#!/bin/bash

if [ -z "$1" ]; then
    sudo docker ps | grep inode_modbus | awk '{print $1}' | xargs sudo docker stop
else
    CONTAINER_IDS=$(sudo docker ps -q --filter "ancestor=inode_modbus:$1")
    if [ -z "$CONTAINER_IDS" ]; then
        echo "No containers running with the image name: $IMAGE_NAME"
    else
        sudo docker stop $CONTAINER_IDS
    fi
fi

sudo docker container prune -f
sudo docker image prune -af
sudo docker load -i ./base_image/inode_modbus.zip

if [ -z "$1" ]; then   
    operators=($(ls ./operators/))
    for o in "${operators[@]}"
    do  
        sudo cp Dockerfile ./operators/$o/
        sudo cp requirements.txt ./operators/$o/
        sudo docker build -t inode_modbus:$o ./operators/$o/
        sudo docker run -d --name $o --restart unless-stopped inode_modbus:$o
        sudo rm ./operators/$o/Dockerfile
        sudo rm ./operators/$o/requirements.txt
    done
else
    sudo cp Dockerfile ./operators/$1/
    sudo cp requirements.txt ./operators/$1/
    sudo docker build -t inode_modbus:$1 ./operators/$1/
    sudo docker run -d --name $1 --restart unless-stopped inode_modbus:$1
    sudo rm ./operators/$1/Dockerfile
    sudo rm ./operators/$1/requirements.txt
fi
