#!/usr/bin/env bash

# Exit on error, trace commands, don't allow unset variables,
# pileline status code is 0 iff all commands in pipeline has status code 0
set -eux
exec > >(tee -a /var/log/vault-setup.log) 2>&1

echo "Starting Vault setup at $(date)"

source /etc/environment

VAULT_HOST_IP=${VAULT_HOST_IP:-"127.0.0.1"}
DB_HOST_IP=${DB_HOST_IP}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
OUTPUT_KEYS_FILE=${OUTPUT_KEYS_FILE:-"/root/vault-keys.json"}

# Validate required environment variables
if [[ -z "${DB_HOST_IP}" || -z "${DB_USER}" || -z "${DB_PASSWORD}" ]]; then
	echo "Error: DB_HOST_IP, DB_USER, or DB_PASSWORD not set."
	exit 1
fi

apt update
apt install -y wget jq redis-tools unzip

# Install AWS CLI if not already present
if ! command -v aws &>/dev/null; then
	apt install -y pipx
	pipx ensurepath
	pipx install awscli
	pipx ensurepath
	export PATH=$PATH:/root/.local/bin
	aws --version
fi

# Install HashiCorp Vault if not already present
if [[ ! -f /usr/share/keyrings/hashicorp-archive-keyring.gpg ]]; then
	wget -O - https://apt.releases.hashicorp.com/gpg 2>/dev/null | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
	apt update && apt install -y vault
fi

# Set up Vault directories
export VAULT_DATA=/opt/vault/data
export VAULT_CONFIG=/etc/vault.d

mkdir -p ${VAULT_DATA}
mkdir -p ${VAULT_CONFIG}

# Set necessary capabilities for Vault to lock memory
setcap cap_ipc_lock=+ep $(readlink -f $(which vault))

# Set appropriate permissions on Vault data directory
chown -R vault:vault ${VAULT_DATA}
chmod -R 750 ${VAULT_DATA}

# Overwrite Vault configuration file
cat >${VAULT_CONFIG}/vault.hcl <<EOF
ui = false
api_addr = "http://${VAULT_HOST_IP}:8200"
disable_mlock = false

storage "file" {
	path = "/opt/vault/data"
}

listener "tcp" {
	address = "0.0.0.0:8200"
	tls_disable = "true"
}
EOF

# Set permissions on Vault config file
chown vault:vault "${VAULT_CONFIG}/vault.hcl"
chmod 640 "${VAULT_CONFIG}/vault.hcl"

# Start Vault service
systemctl enable vault
if systemctl is-active --quiet vault; then
    systemctl restart vault
else
    systemctl start vault
fi


# Set Vault API address for CLI commands
export VAULT_ADDR="http://${VAULT_HOST_IP}:8200"

touch ${OUTPUT_KEYS_FILE}

# Initialize Vault if not already initialized
if ! jq -e '.unseal_keys_b64 // empty' "${OUTPUT_KEYS_FILE}" >/dev/null; then
	INIT_RESPONSE=$(vault operator init -key-shares=3 -key-threshold=2 -format=json)

	echo "${INIT_RESPONSE}" >${OUTPUT_KEYS_FILE}
	chmod 600 ${OUTPUT_KEYS_FILE}
fi

# Unseal Vault if currently sealed
if vault status -format=json 2>/dev/null | grep -q '"sealed": true'; then
	echo "Vault is sealed. Unsealing Vault..."

	UNSEAL_KEY_1=$(jq -r .unseal_keys_b64[0] "${OUTPUT_KEYS_FILE}")
	UNSEAL_KEY_2=$(jq -r .unseal_keys_b64[1] "${OUTPUT_KEYS_FILE}")

	vault operator unseal "${UNSEAL_KEY_1}"
	vault operator unseal "${UNSEAL_KEY_2}"
fi

# Authenticate with root token
echo "Authenticating with root token..."
ROOT_TOKEN=$(jq -r .root_token "${OUTPUT_KEYS_FILE}")
export VAULT_TOKEN="${ROOT_TOKEN}"

# Skip configuration if already done
if jq -e '.approle.role_id // empty' "${OUTPUT_KEYS_FILE}" >/dev/null; then
	echo "Configuration already been done."
	exit 0
fi

echo "Configuring secrets and authentication..."
vault secrets enable database

# Configure MySQL database connection
# This will create database conneciton when executed
# So your database should be up and running
vault write database/config/mysql-database \
	plugin_name=mysql-database-plugin \
	connection_url="{{username}}:{{password}}@tcp(${DB_HOST_IP}:3306)/" \
	allowed_roles="nodejs-app" \
	username="${DB_USER}" \
	password="${DB_PASSWORD}"

# Set up database role for the nodejs application
vault write database/roles/nodejs-app \
	db_name=mysql-database \
	creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'; GRANT SELECT, INSERT, UPDATE ON ${DB_NAME}.* TO '{{name}}'@'%';" \
	default_ttl="1h" \
	max_ttl="24h"

# Enable AppRole authentication method
vault auth enable approle

# Create policy for nodejs application access
cat >nodejs-policy.hcl <<EOF
path "database/creds/nodejs-app" {
	capabilities = ["read"]
}
EOF

vault policy write nodejs-policy nodejs-policy.hcl

# Configure AppRole with appropriate policies and TTLs
vault write auth/approle/role/nodejs-role \
	token_policies="nodejs-policy" \
	token_ttl=1h \
	token_max_ttl=24h

# Generate and retrieve role_id and secret_id
ROLE_ID=$(vault read -format=json auth/approle/role/nodejs-role/role-id | jq -r .data.role_id)
SECRET_ID=$(vault write -f -format=json auth/approle/role/nodejs-role/secret-id | jq -r .data.secret_id)

# Add AppRole credentials to keys file
jq --arg role_id "$ROLE_ID" --arg secret_id "$SECRET_ID" \
	'. + {approle: {role_id: $role_id, secret_id: $secret_id}}' ${OUTPUT_KEYS_FILE} >${OUTPUT_KEYS_FILE}.tmp &&
	mv ${OUTPUT_KEYS_FILE}.tmp ${OUTPUT_KEYS_FILE}

# Store credentials in AWS SSM Parameter Store
aws ssm put-parameter --name "role_id" --value "${ROLE_ID}" --type "String" --overwrite --region "ap-southeast-1"
aws ssm put-parameter --name "secret_id" --value "${SECRET_ID}" --type "String" --overwrite --region "ap-southeast-1"

echo "Vault setup completed successfully at $(date)"