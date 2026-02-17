#!/bin/bash

mkdir app_build
cp app/main.py app_build/
cp app/dependencies.py app_build/
cp app/middleware.py app_build/
cp app/requirements.txt app_build/
cp app/prestart.sh app_build/
cp -r app/routers/ app_build/
cp -r app/etc/ app_build/
cp -r app/monitoring/ app_build/
find app_build/ -type d -name '__pycache__' -exec rm -r {} +
mkdir app_build/logs/

VERSION=$(cat VERSION | tr -d '\n')
sudo docker build -t "lrde-backend:${VERSION}" .

rm -r app_build/

sudo docker save -o "lrde-backend-${VERSION}.tar" "lrde-backend:${VERSION}"
