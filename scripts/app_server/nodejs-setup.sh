#!/usr/bin/env bash

# Exit on error, trace commands, don't allow unset variables,
# pileline status code is 0 iff all commands in pipeline has status code 0
set -euxo pipefail
exec > >(tee -a "/var/log/nodejs-setup.log") 2>&1

echo "Starting NodeJS setup at $(date)"

source /etc/environment

# Function to safely retrieve AWS SSM parameters
function get_ssm_parameter() {
    local param_name="$1"
    local max_attempts=3
    local attempt=1

    while (($attempt < $max_attempts)); do
        echo "Retrieving SSM parameter $param_name (attempt $attempt/$max_attempts)" >&2
        local value
        if value=$(aws ssm get-parameter --name "$param_name" --query "Parameter.Value" --output text --region "$REGION_NAME" 2>/dev/null); then
            echo "$value"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "Failed to retrieve SSM parameter, retrying in 5 seconds..." >&2
        sleep 5
    done

    echo "Failed to retrieve SSM parameter $param_name after $max_attempts attempts" >&2
    return 1
}

# Main script execution
function main() {
    apt update
    apt install -y netcat-openbsd git unzip curl

    # Install Node.js from NodeSource repository for more recent version
    if ! command -v nodejs &>/dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
        apt install -y nodejs
    fi

    # Install AWS CLI if not present
    if ! command -v aws &>/dev/null; then
        apt install -y pipx
        export PATH="$PATH:~/.local/bin"
        pipx ensurepath
        pipx install awscli
    fi

    # Create dedicated user for running the application
    if ! id -u nodejs &>/dev/null; then
        useradd --system --create-home --home-dir /opt/nodejs --shell /bin/false nodejs
    fi

    # Clone application repository
    APP_DIR="/opt/app"
    if [[ ! -d "$APP_DIR" ]]; then
        git clone https://github.com/kcnaiamh/Demo-App-1.git "$APP_DIR"
    else
        echo "Application directory already exists"
    fi

    # Install Node.js dependencies
    cd "$APP_DIR"
    npm install

    # Setup environment configuration
    cp "$APP_DIR/src/.env.example" "$APP_DIR/src/.env"

    # Get external IP with fallback options
    HOST_IP=$(curl -s ip.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || curl -s ifconfig.me 2>/dev/null)

    # Get Vault credentials from AWS SSM Parameter Store
    ROLE_ID=$(get_ssm_parameter "role_id")
    SECRET_ID=$(get_ssm_parameter "secret_id")

    # Update environment configuration
    sed -i "s|^HOST_IP=.*|HOST_IP='${HOST_IP}'|" "$APP_DIR/src/.env"
    sed -i "s|^MYSQL_HOST_IP=.*|MYSQL_HOST_IP='${DB_HOST_IP}'|" "$APP_DIR/src/.env"
    sed -i "s|^MYSQL_DATABASE=.*|MYSQL_DATABASE='${DB_NAME}'|" "$APP_DIR/src/.env"
    sed -i "s|^VAULT_ADDR=.*|VAULT_ADDR='http://${VAULT_HOST_IP}:8200'|" "$APP_DIR/src/.env"
    sed -i "s|^REDIS_HOST=.*|REDIS_HOST='${REDIS_HOST_IP}'|" "$APP_DIR/src/.env"
    sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD='${REDIS_PASSWORD}'|" "$APP_DIR/src/.env"
    sed -i "s|^VAULT_ROLE_ID=.*|VAULT_ROLE_ID='${ROLE_ID}'|" "$APP_DIR/src/.env"
    sed -i "s|^VAULT_SECRET_ID=.*|VAULT_SECRET_ID='${SECRET_ID}'|" "$APP_DIR/src/.env"

    # Secure permissions
    chown -R nodejs:nodejs "$APP_DIR"
    chmod -R 750 "$APP_DIR"
    chmod 640 "$APP_DIR/src/.env"

    systemctl enable --now nodejs-app
    echo "NodeJS setup completed successfully at $(date)"
}

main
