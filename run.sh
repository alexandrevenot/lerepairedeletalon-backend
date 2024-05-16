#!/bin/bash

sudo docker run -d --name api_container -p 3001:80 -v /lerepairedeletalon/server/app/logs:/app/logs/ -e ACCESS_LOG=/app/logs/access.log -e ERROR_LOG=/app/logs/error.log api:0.0.0
