#!/bin/sh
set -eu
umask 077
# Only initialize this app's volume directories; never recursively chown data.
for directory in /data /data/profile /data/runs /data/workspace; do
    install -d -m 700 -o hermes -g hermes "$directory"
done
gosu hermes /opt/hermes/.venv/bin/python /opt/lab/lab.py init
cd /data/workspace
exec gosu hermes "$@"
