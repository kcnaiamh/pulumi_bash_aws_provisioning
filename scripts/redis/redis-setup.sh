#!/usr/bin/env bash

# Exit on error, trace commands, don't allow unset variables,
# pileline status code is 0 iff all commands in pipeline has status code 0
set -euxo pipefail
exec > >(tee -a /var/log/redis-setup.log) 2>&1

echo "Starting Redis setup at $(date)"

source /etc/environment

apt update && apt install -y lsb-release curl gpg

# ---------------------------------------------------------------------------- #
# INSTALL REDIS
# ---------------------------------------------------------------------------- #

curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list
apt update
apt install -y redis

# ---------------------------------------------------------------------------- #
# CONFIGURE REDIS
# ---------------------------------------------------------------------------- #

REDIS_CONF="/etc/redis/redis.conf"

# Backup original configuration
cp -f "$REDIS_CONF" "${REDIS_CONF}.bak"

# Security settings
sed -i 's/^bind .*/bind 0.0.0.0/' ${REDIS_CONF}
sed -i 's/^protected-mode no/protected-mode yes/' ${REDIS_CONF}
sed -i "s/^# requirepass .*/requirepass ${REDIS_PASSWORD}/" ${REDIS_CONF}

# Performance settings
sed -i 's/^# maxmemory .*/maxmemory 256mb/' ${REDIS_CONF}
sed -i 's/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/' ${REDIS_CONF}

# Persistence settings
sed -i 's/^save 900 1/save 60 1/' ${REDIS_CONF}
sed -i 's/^save 300 10/# save 300 10/' ${REDIS_CONF}
sed -i 's/^save 60 10000/# save 60 10000/' ${REDIS_CONF}
sed -i 's/^# appendonly no/appendonly yes/' ${REDIS_CONF}

# Service settings
sed -i 's/^supervised no/supervised systemd/' ${REDIS_CONF}
sed -i 's/^daemonize no/daemonize yes/' ${REDIS_CONF}

# Additional hardening
echo "tcp-backlog 128" >>"$REDIS_CONF"
echo "timeout 30" >>"$REDIS_CONF"
echo "rename-command FLUSHALL \"\"" >>"$REDIS_CONF"
echo "rename-command FLUSHDB \"\"" >>"$REDIS_CONF"
echo "rename-command CONFIG \"\"" >>"$REDIS_CONF"

systemctl enable redis-server
systemctl restart redis-server

echo "Redis setup completed successfully at $(date)"
