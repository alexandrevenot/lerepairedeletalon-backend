#!/bin/bash
set -e

VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')

docker build -t "lrde-backend:${VERSION}" .

docker save -o "lrde-backend-${VERSION}.tar" "lrde-backend:${VERSION}"
