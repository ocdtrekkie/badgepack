#!/bin/bash
set -euo pipefail
VENV=/opt/app-venv
cd /opt/app

wait_for() {
    local service=$1
    local file=$2
    while [ ! -e "$file" ] ; do
        echo "waiting for $service to be available at $file."
        sleep .1
    done
}

# something something folders
mkdir -p /var/lib/nginx
mkdir -p /var/log
mkdir -p /var/log/nginx
# Wipe /var/run, since pidfiles and socket files from previous launches should go away
# TODO someday: I'd prefer a tmpfs for these.
rm -rf /var/run
mkdir -p /var/run
rm -rf /var/tmp
mkdir -p /var/tmp

# Rotate log files larger than 512K
log_files="$(find /var/log -type f -name '*.log')"
for f in $log_files; do
    if [ $(du -b "$f" | awk '{print $1}') -ge $((512 * 1024)) ] ; then
        mv $f $f.1
    fi
done

UWSGI_SOCKET_FILE=/var/run/uwsgi.sock

# Start our powerbox proxy server, and wait for it to write the cert:
export DB_TYPE=sqlite3
export DB_URI="/var/badges.db"
export CA_CERT_PATH=/var/ca-spoof-cert.pem
rm -f $CA_CERT_PATH
/opt/powerbox-http-proxy/powerbox-http-proxy &
wait_for "root cert" "$CA_CERT_PATH"

export http_proxy=http://127.0.0.1:$POWERBOX_PROXY_PORT
export https_proxy=http://127.0.0.1:$POWERBOX_PROXY_PORT

# Spawn uwsgi
HOME=/var uwsgi \
        --socket $UWSGI_SOCKET_FILE \
        --plugin python3 \
        --virtualenv $VENV \
        --wsgi-file /opt/app/app.py \
        --enable-threads \
        --threads 2 \
        --processes 2 \
        --post-buffering 16777216 \
        --single-interpreter \
        --callable app &

# Wait for uwsgi to bind its socket
wait_for uwsgi $UWSGI_SOCKET_FILE

# Start nginx.
/usr/sbin/nginx -c /opt/app/.sandstorm/service-config/nginx.conf -g "daemon off;"

exit 0
