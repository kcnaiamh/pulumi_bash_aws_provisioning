import pulumi
import pulumi_aws as aws
from utils import read_file, gen_password

def create_instances(network, security_groups, iam_profile, config):
    """Create EC2 instances for each component"""

    DB_NAME = config["db_name"]
    DB_VAULT_USER = config["db_vault_user"]
    SSH_KEY_NAME = config["ssh_key_name"]
    aws_key = config["aws_key"]
    REGION_NAME = aws.get_region().name

    # Generate passwords
    REDIS_PASSWORD = gen_password(12)
    DB_VAULT_PASS = gen_password(12)

    # Read script files
    redis_setup_script = read_file('scripts/redis/redis-setup.sh')
    mysql_setup_script = read_file('scripts/mysql/mysql-setup.sh')
    mysql_hcheck_script = read_file('scripts/mysql/mysql-check.sh')
    mysql_hcheck_service = read_file('scripts/mysql/mysql-check.service')
    db_schema = read_file('scripts/mysql/schema.sql')
    vault_setup_script = read_file('scripts/vault/vault-setup.sh')
    vault_hcheck_script = read_file('scripts/vault/vault-check.sh')
    vault_hcheck_service = read_file('scripts/vault/vault-check.service')
    nodejs_setup_script = read_file('scripts/app_server/nodejs-setup.sh')
    nodejs_app_service = read_file('scripts/app_server/nodejs-app.service')

    # Create Redis instance
    def generate_redis_user_data(redis_password):
        return f'''\
#!/usr/bin/env bash
set -euxo pipefail
exec > >(tee /var/log/redis-userdata.log) 2>&1

apt update && apt install -y gpg

mkdir -p /usr/local/bin

echo "REDIS_PASSWORD={redis_password}" >> /etc/environment

cat > /usr/local/bin/redis-setup.sh << 'EOF'
{redis_setup_script}
EOF

chmod +x /usr/local/bin/redis-setup.sh

/usr/local/bin/redis-setup.sh && \
rm /usr/local/bin/redis-setup.sh
'''

    redis_ec2 = aws.ec2.Instance(
        resource_name = 'redis-server',
        instance_type = 't2.micro',
        ami = 'ami-01811d4912b4ccb26',
        subnet_id = network["private_subnet"].id,
        key_name = SSH_KEY_NAME,
        vpc_security_group_ids=[
            security_groups["redis"].id
        ],
        user_data=pulumi.Output.all(REDIS_PASSWORD).apply(
            lambda args: generate_redis_user_data(args[0]),
        ),
        user_data_replace_on_change=True,
        tags = {
            'Name': 'redis-server'
        },
        opts=pulumi.ResourceOptions(
            depends_on=[
                network["nat_gateway"],
                network["private_route_table_association"],
                network["private_subnet"]
            ] + ([aws_key] if aws_key else [])
        )
    )

    # Create MySQL instance
    def generate_mysql_user_data(redis_host_ip, redis_pass, db_vault_pass, private_subnet_cidr):
        return f'''\
#!/usr/bin/env bash
set -euxo pipefail
exec > >(tee /var/log/mysql-userdata.log) 2>&1

echo "REDIS_HOST_IP={redis_host_ip}" >> /etc/environment
echo "REDIS_PASSWORD={redis_pass}" >> /etc/environment
echo "DB_ROOT_PASS={gen_password(12)}" >> /etc/environment
echo "DB_NAME={DB_NAME}" >> /etc/environment
echo "DB_VAULT_USER={DB_VAULT_USER}" >> /etc/environment
echo "DB_VAULT_PASS={db_vault_pass}" >> /etc/environment
echo "PRIVATE_SUBNET_CIDR={private_subnet_cidr}" >> /etc/environment

apt update

mkdir -p /usr/local/bin

cat > /usr/local/bin/mysql-check.sh << 'EOF'
{mysql_hcheck_script}
EOF

cat > /etc/systemd/system/mysql-check.service << 'EOF'
{mysql_hcheck_service}
EOF

cat > /usr/local/bin/mysql-setup.sh << 'FINAL'
{mysql_setup_script}
FINAL

cat > /tmp/schema.sql << 'EOF'
{db_schema}
EOF

chmod u+x /usr/local/bin/mysql-check.sh
chmod +x /usr/local/bin/mysql-setup.sh


/usr/local/bin/mysql-setup.sh && \
rm /usr/local/bin/mysql-setup.sh

chown mysql:mysql /usr/local/bin/mysql-check.sh
chmod 500 /usr/local/bin/mysql-check.sh

systemctl enable --now mysql-check.service
'''

    db = aws.ec2.Instance(
        resource_name = 'db-server',
        instance_type = 't2.micro',
        ami = 'ami-01811d4912b4ccb26',
        subnet_id = network["private_subnet"].id,
        key_name = SSH_KEY_NAME,
        vpc_security_group_ids=[
            security_groups["db"].id
        ],
        user_data=pulumi.Output.all(redis_ec2.private_ip, REDIS_PASSWORD, DB_VAULT_PASS, network["private_subnet"].cidr_block).apply(
            lambda args: generate_mysql_user_data(*args),
        ),
        user_data_replace_on_change=True,
        tags = {
            'Name': 'db-server'
        },
        opts=pulumi.ResourceOptions(
            depends_on=[
                redis_ec2
            ] + ([aws_key] if aws_key else [])
        )
    )

    # Create Vault instance
    def generate_vault_user_data(redis_host_ip, redis_pass, db_host_ip, db_user, db_pass):
        return f'''\
#!/usr/bin/env bash
set -euxo pipefail
exec > >(tee /var/log/vault-userdata.log) 2>&1

echo "REDIS_HOST_IP={redis_host_ip}" >> /etc/environment
echo "REDIS_PASSWORD={redis_pass}" >> /etc/environment
echo "DB_HOST_IP={db_host_ip}" >> /etc/environment
echo "DB_USER={db_user}" >> /etc/environment
echo "DB_PASSWORD={db_pass}" >> /etc/environment
echo "DB_NAME={DB_NAME}" >> /etc/environment


apt update

mkdir -p /usr/local/bin

cat > /usr/local/bin/vault-check.sh << 'EOF'
{vault_hcheck_script}
EOF

cat > /etc/systemd/system/vault-check.service << 'EOF'
{vault_hcheck_service}
EOF

cat > /usr/local/bin/vault-setup.sh << 'FINAL'
{vault_setup_script}
FINAL

chmod u+x /usr/local/bin/vault-check.sh
chmod 500 /usr/local/bin/vault-setup.sh


/usr/local/bin/vault-setup.sh

chown vault:vault /usr/local/bin/vault-check.sh
chmod 500 /usr/local/bin/vault-check.sh

systemctl enable --now vault-check.service
'''

    vault_ec2 = aws.ec2.Instance(
        resource_name = 'vault-server',
        instance_type = 't2.micro',
        ami = 'ami-01811d4912b4ccb26',
        iam_instance_profile=iam_profile.name,
        subnet_id = network["private_subnet"].id,
        key_name = SSH_KEY_NAME,
        vpc_security_group_ids=[
            security_groups["vault"].id
        ],
        user_data=pulumi.Output.all(redis_ec2.private_ip, REDIS_PASSWORD, db.private_ip, DB_VAULT_USER, DB_VAULT_PASS).apply(
            lambda args: generate_vault_user_data(*args),
        ),
        user_data_replace_on_change=True,
        tags = {
            'Name': 'vault-server'
        },
        opts=pulumi.ResourceOptions(
            depends_on=[
                db
            ] + ([aws_key] if aws_key else [])
        )
    )

    # Create Node.js instance
    def generate_nodejs_user_data(redis_host_ip, db_host_ip, vault_host_ip, redis_pass):
        return f'''\
#!/usr/bin/env bash
set -euxo pipefail
exec > >(tee /var/log/nodejs-userdata.log) 2>&1

echo "REDIS_HOST_IP={redis_host_ip}" >> /etc/environment
echo "REDIS_PASSWORD={redis_pass}" >> /etc/environment
echo "DB_HOST_IP={db_host_ip}" >> /etc/environment
echo "VAULT_HOST_IP={vault_host_ip}" >> /etc/environment
echo "DB_NAME={DB_NAME}" >> /etc/environment
echo "REGION_NAME={REGION_NAME}" >> /etc/environment

apt update

mkdir -p /usr/local/bin
mkdir -p /opt/app

cat > /usr/local/bin/nodejs-setup.sh << 'EOF'
{nodejs_setup_script}
EOF

cat > /etc/systemd/system/nodejs-app.service << 'EOF'
{nodejs_app_service}
EOF


chmod +x /usr/local/bin/nodejs-setup.sh

/usr/local/bin/nodejs-setup.sh
'''

    nodejs = aws.ec2.Instance(
        resource_name='nodejs-server',
        instance_type='t2.micro',
        ami='ami-01811d4912b4ccb26',
        iam_instance_profile=iam_profile.name,
        subnet_id=network["public_subnet"].id,
        key_name=SSH_KEY_NAME,
        vpc_security_group_ids=[
            security_groups["nodejs"].id
        ],
        associate_public_ip_address=True,
        user_data=pulumi.Output.all(redis_ec2.private_ip, db.private_ip, vault_ec2.private_ip, REDIS_PASSWORD).apply(
            lambda args: generate_nodejs_user_data(*args)
        ),
        user_data_replace_on_change=True,
        tags={
            'Name': 'nodejs-server'
        },
        opts=pulumi.ResourceOptions(
            depends_on=[vault_ec2] + ([aws_key] if aws_key else [])
        )
    )

    return {
        "nodejs": nodejs,
        "db": db,
        "redis": redis_ec2,
        "vault": vault_ec2
    }