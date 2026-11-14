#!/bin/sh
set -eu
umask 077
if [ "$(id -u)" = 0 ]; then
    exec gosu hermes /opt/hermes/.venv/bin/python /opt/lab/lab.py "$@"
fi
exec /opt/hermes/.venv/bin/python /opt/lab/lab.py "$@"
