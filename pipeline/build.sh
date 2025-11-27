#!/bin/sh
# Set the -e option
set -e

pip install --upgrade pip
pip install --upgrade hatch
pip install --upgrade twine
hatch run lint
hatch run test
hatch build
