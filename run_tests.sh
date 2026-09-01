#!/bin/bash
set -e
docker build -f Dockerfile.test -t ds-loader-test .
docker run --rm ds-loader-test "$@"
