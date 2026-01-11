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

# Start our powerbox proxy server, and wait for it to write the cert:
export DB_TYPE=sqlite3
export DB_URI="/var/badges.db"
export CA_CERT_PATH=/var/ca-spoof-cert.pem
rm -f $CA_CERT_PATH
/opt/powerbox-http-proxy/powerbox-http-proxy &
wait_for "root cert" "$CA_CERT_PATH"

export http_proxy=http://127.0.0.1:$POWERBOX_PROXY_PORT
export https_proxy=http://127.0.0.1:$POWERBOX_PROXY_PORT

# Change app.py to your app's filename
$VENV/bin/python3 app.py

exit 0
