#!/usr/bin/env bash
set -ex
exec > >(tee -a /var/log/vault-setup.log) 2>&1

source /etc/environment

VAULT_HOST_IP=${VAULT_HOST_IP:-"127.0.0.1"}
DB_HOST_IP=${DB_HOST_IP}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
OUTPUT_KEYS_FILE=${OUTPUT_KEYS_FILE:-"/root/vault-keys.json"}

if [[ -z "${DB_HOST_IP}" || -z "${DB_USER}" || -z "${DB_PASSWORD}" ]]; then
	echo "Error: DB_HOST_IP, DB_USER, or DB_PASSWORD not set."
	exit 1
fi

apt update && apt install -y wget jq redis-tools unzip

if ! command -v aws &>/dev/null; then
	curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" 2>/dev/null
	unzip awscliv2.zip
	./aws/install
fi

if [[ ! -f /usr/share/keyrings/hashicorp-archive-keyring.gpg ]]; then
	wget -O - https://apt.releases.hashicorp.com/gpg 2>/dev/null | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
	apt update && apt install -y vault
fi

export VAULT_DATA=/opt/vault/data
export VAULT_CONFIG=/etc/vault.d

mkdir -p ${VAULT_DATA}
mkdir -p ${VAULT_CONFIG}

setcap cap_ipc_lock=+ep $(readlink -f $(which vault))

chown -R vault:vault ${VAULT_DATA}
chmod -R 750 ${VAULT_DATA}

cat >${VAULT_CONFIG}/vault.hcl <<EOF
ui = true
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

chown vault:vault "${VAULT_CONFIG}/vault.hcl"
chmod 640 "${VAULT_CONFIG}/vault.hcl"

systemctl enable vault
systemctl start vault

export VAULT_ADDR="http://${VAULT_HOST_IP}:8200"

touch ${OUTPUT_KEYS_FILE}

if ! jq -e '.unseal_keys_b64 // empty' "${OUTPUT_KEYS_FILE}" >/dev/null; then
	INIT_RESPONSE=$(vault operator init -key-shares=3 -key-threshold=2 -format=json)

	echo "${INIT_RESPONSE}" >${OUTPUT_KEYS_FILE}
	chmod 600 ${OUTPUT_KEYS_FILE}
fi

if vault status -format=json 2>/dev/null | grep -q '"sealed": true'; then
	echo "Vault is sealed. Unsealing Vault..."

	UNSEAL_KEY_1=$(jq -r .unseal_keys_b64[0] "${OUTPUT_KEYS_FILE}")
	UNSEAL_KEY_2=$(jq -r .unseal_keys_b64[1] "${OUTPUT_KEYS_FILE}")

	vault operator unseal "${UNSEAL_KEY_1}"
	vault operator unseal "${UNSEAL_KEY_2}"
fi

echo "Authenticating with root token..."
ROOT_TOKEN=$(jq -r .root_token "${OUTPUT_KEYS_FILE}")
export VAULT_TOKEN="${ROOT_TOKEN}"

if jq -e '.approle.role_id // empty' "${OUTPUT_KEYS_FILE}" >/dev/null; then
	echo "Configuration already been done."
	exit 0
fi

echo "Configuring secrets and authentication..."
vault secrets enable database

# CAUTION: This will make database conneciton when executed
vault write database/config/mysql-database \
	plugin_name=mysql-database-plugin \
	connection_url="{{username}}:{{password}}@tcp(${DB_HOST_IP}:3306)/" \
	allowed_roles="nodejs-app" \
	username="${DB_USER}" \
	password="${DB_PASSWORD}"

vault write database/roles/nodejs-app \
	db_name=mysql-database \
	creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'; GRANT SELECT, INSERT, UPDATE ON ${DB_NAME}.* TO '{{name}}'@'%';" \
	default_ttl="1h" \
	max_ttl="24h"

vault auth enable approle

cat >nodejs-policy.hcl <<EOF
path "database/creds/nodejs-app" {
	capabilities = ["read"]
}
EOF

vault policy write nodejs-policy nodejs-policy.hcl

vault write auth/approle/role/nodejs-role \
	token_policies="nodejs-policy" \
	token_ttl=1h \
	token_max_ttl=24h

ROLE_ID=$(vault read -format=json auth/approle/role/nodejs-role/role-id | jq -r .data.role_id)
SECRET_ID=$(vault write -f -format=json auth/approle/role/nodejs-role/secret-id | jq -r .data.secret_id)

jq --arg role_id "$ROLE_ID" --arg secret_id "$SECRET_ID" \
	'. + {approle: {role_id: $role_id, secret_id: $secret_id}}' ${OUTPUT_KEYS_FILE} >${OUTPUT_KEYS_FILE}.tmp &&
	mv ${OUTPUT_KEYS_FILE}.tmp ${OUTPUT_KEYS_FILE}

aws ssm put-parameter --name "role_id" --value "${ROLE_ID}" --type "String" --overwrite --region "ap-southeast-1"
aws ssm put-parameter --name "secret_id" --value "${SECRET_ID}" --type "String" --overwrite --region "ap-southeast-1"

echo "Vault setup completed successfully!"
echo "Vault keys and tokens saved to: ${OUTPUT_KEYS_FILE}"
echo "Keep this file secure!"
