#!/usr/bin/env bash
set -ex
exec > >(tee -a /var/log/mysql-setup.log) 2>&1

source /etc/environment

# MySQL Configurations
DB_ROOT_PASS="${DB_ROOT_PASS}"
DB_NAME="${DB_NAME}"
DB_VAULT_USER="${DB_VAULT_USER}"
DB_VAULT_PASS="${DB_VAULT_PASS}"
PRIVATE_SUBNET="$(echo "${PRIVATE_SUBNET_CIDR}" | awk -F'[./]' '{print $1"."$2"."$3".%"}')"


apt update && apt install -y mysql-server redis-tools


if ! systemctl is-active --quiet mysql.service; then
    echo 'MySQL server is not running. Starting MySQL server...'
    systemctl enable --now mysql
fi


echo "Configuring MySQL for remote access..."
sed -i 's/bind-address\s*=.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
systemctl restart mysql


mysql --defaults-file=/etc/mysql/debian.cnf -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '${DB_ROOT_PASS}'; FLUSH PRIVILEGES;"


cat > /root/.my.cnf <<EOF
[client]
user=root
password="${DB_ROOT_PASS}"
EOF

chmod 600 /root/.my.cnf


# mysql_secure_installation
mysql --defaults-file=/root/.my.cnf <<EOF
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DROP DATABASE IF EXISTS test; DELETE FROM mysql.db WHERE Db='test';
FLUSH PRIVILEGES;
EOF


mysql --defaults-file=/root/.my.cnf <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME};
CREATE USER IF NOT EXISTS '${DB_VAULT_USER}'@'${PRIVATE_SUBNET}' IDENTIFIED WITH caching_sha2_password BY '${DB_VAULT_PASS}';
GRANT CREATE USER ON *.* TO '${DB_VAULT_USER}'@'${PRIVATE_SUBNET}';
GRANT SELECT, INSERT, UPDATE, GRANT OPTION ON ${DB_NAME}.* TO '${DB_VAULT_USER}'@'${PRIVATE_SUBNET}';
FLUSH PRIVILEGES;
EOF


# Define Schema in a Separate SQL File
cat > /tmp/schema.sql <<EOF
USE ${DB_NAME};
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT IGNORE INTO users (username, email) VALUES
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com'),
    ('charlie', 'charlie@example.com');
EOF


# Load Schema
mysql --defaults-file=/root/.my.cnf < /tmp/schema.sql
rm -f /tmp/schema.sql  # Cleanup

echo "MySQL setup completed successfully!"