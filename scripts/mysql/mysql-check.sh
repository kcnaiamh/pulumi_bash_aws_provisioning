#!/usr/bin/env bash
set -euxo pipefail
exec > >(tee -a /var/log/mysql-check.log) 2>&1

source /etc/environment

RETRY_INTERVAL=5
REDIS_HOST="${REDIS_HOST_IP}"
REDIS_PASS="${REDIS_PASSWORD}"
CHANNEL="health:mysql"
STATUS="UNKNOWN"
TTL=1200
REDIS_PORT=6379

publish_status() {
    local new_status="$1"
    if [[ "$STATUS" != "$new_status" ]]; then
        echo "Publishing status: $new_status"
        REDISCLI_AUTH="$REDIS_PASS" redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PUBLISH "$CHANNEL" "$new_status"
        STATUS="$new_status"
    fi
}

if systemctl is-active --quiet mysql; then
    REDISCLI_AUTH="$REDIS_PASS" redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$CHANNEL" "UP" EX "$TTL"
else
    REDISCLI_AUTH="$REDIS_PASS" redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$CHANNEL" "DOWN" EX "$TTL"
fi

while true; do
    if systemctl is-active --quiet mysql; then
        publish_status "UP"
    else
        publish_status "DOWN"
    fi
    sleep "$RETRY_INTERVAL"
done
