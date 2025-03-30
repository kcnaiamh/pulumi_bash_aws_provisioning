#!/bin/bash
set -ex
exec > >(tee -a /var/log/redis-setup.log) 2>&1

source /etc/environment

apt update && apt install -y lsb-release curl gpg

curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list
apt update
apt install -y redis


sed -i 's/^bind .*/bind 0.0.0.0/' /etc/redis/redis.conf
sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf
sed -i "s/^# requirepass .*/requirepass ${REDIS_PASSWORD}/" /etc/redis/redis.conf
sed -i 's/^# maxmemory .*/maxmemory 256mb/' /etc/redis/redis.conf
sed -i 's/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
sed -i 's/^save 900 1/save 60 1/' /etc/redis/redis.conf
sed -i 's/^save 300 10/# save 300 10/' /etc/redis/redis.conf
sed -i 's/^save 60 10000/# save 60 10000/' /etc/redis/redis.conf
sed -i 's/^# appendonly no/appendonly yes/' /etc/redis/redis.conf
sed -i 's/^protected-mode no/protected-mode yes/' /etc/redis/redis.conf
sed -i 's/^daemonize no/daemonize yes/' /etc/redis/redis.conf

systemctl enable redis-server
systemctl restart redis-server

echo "Redis Setup Complete! Use 'redis-cli -a ${REDIS_PASSWORD}' to connect."
