#! /bin/bash

sudo docker ps | grep inode_modbus | awk '{print $1}' | xargs sudo docker restart