#!/bin/bash

# When you change this file, you must take manual action. Read this doc:
# - https://docs.sandstorm.io/en/latest/vagrant-spk/customizing/#setupsh

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y build-essential python3-dev python3-pip python3-venv pipenv sqlite3 git

# The version of golang in the debian repositories tends to be incredibly
# out of date; let's get ourselves a newer version from upstream:
if [ -e /opt/app/.sandstorm/go-version ]; then
    # Get the same version we've used before
    curl -L "https://go.dev/dl/$(cat '/opt/app/.sandstorm/go-version').linux-amd64.tar.gz" -o go.tar.gz
else
    # Get the newest version for a new project
    curl -L "https://go.dev/dl/$(curl 'https://go.dev/VERSION?m=text' | head -n 1).linux-amd64.tar.gz" -o go.tar.gz
fi
tar -C /usr/local -xzf go.tar.gz
rm go.tar.gz
echo 'export PATH=/usr/local/go/bin:$PATH' > /etc/profile.d/go.sh

# Get the same version next time
/usr/local/go/bin/go version | cut -d ' ' -f 3 > /opt/app/.sandstorm/go-version

cd /opt && git clone https://github.com/sandstorm-org/powerbox-http-proxy
cd /opt/powerbox-http-proxy && /usr/local/go/bin/go build

exit 0
