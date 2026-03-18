#!/bin/sh
# Ensure /data is writable by the runner user, then drop privileges
chown runner:runner /data
exec su -s /bin/sh runner -c "exec $*"
