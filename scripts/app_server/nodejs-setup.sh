#!/usr/bin/env bash
set -ex
exec > >(tee -a /var/log/nodejs-setup.log) 2>&1

source /etc/environment

apt update && apt install -y netcat-openbsd git unzip nodejs npm

curl -v "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" 2>/dev/null
unzip awscliv2.zip
./aws/install

useradd -r -s /bin/false nodejs

git clone https://github.com/kcnaiamh/Demo-App-1.git /opt/app/
cd /opt/app

npm install

mv /opt/app/src/.env.example /opt/app/src/.env

HOST_IP=$(curl ip.me 2>/dev/null)
ROLE_ID=$(aws ssm get-parameter --name "role_id" --query "Parameter.Value" --output text --region "ap-southeast-1")
SECRET_ID=$(aws ssm get-parameter --name "secret_id" --query "Parameter.Value" --output text --region "ap-southeast-1")

sed -i "s/^HOST_IP=.*/HOST_IP='${HOST_IP}'/" /opt/app/src/.env
sed -i "s/^MYSQL_HOST_IP=.*/MYSQL_HOST_IP='${DB_HOST_IP}'/" /opt/app/src/.env
sed -i "s/^MYSQL_DATABASE=.*/MYSQL_DATABASE='${DB_NAME}'/" /opt/app/src/.env
sed -i "s^VAULT_ADDR=.*^VAULT_ADDR='http://${VAULT_HOST_IP}:8200'^" /opt/app/src/.env
sed -i "s/^REDIS_HOST=.*/REDIS_HOST='${REDIS_HOST_IP}'/" /opt/app/src/.env
sed -i "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD='${REDIS_PASSWORD}'/" /opt/app/src/.env
sed -i "s/^VAULT_ROLE_ID=.*/VAULT_ROLE_ID='${ROLE_ID}'/" /opt/app/src/.env
sed -i "s/^VAULT_SECRET_ID=.*/VAULT_SECRET_ID='${SECRET_ID}'/" /opt/app/src/.env

chown -R nodejs:nodejs /opt/app/
systemctl enable --now nodejs-app
