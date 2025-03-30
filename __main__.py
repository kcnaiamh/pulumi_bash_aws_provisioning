import pulumi
import pulumi_aws as aws
import os
import secrets
import string

VPC_CIDR = '10.0.0.0/16'
PRIVATE_SUBNET_CIDR = '10.0.2.0/24'
PUBLIC_SUBNET_CIDR = '10.0.1.0/24'

config = pulumi.Config()
AZ_NAME = f'{aws.get_region()}a'
DB_NAME = config.require("dbName")
DB_VAULT_USER = config.require("dbVaultUser")



def read_file(file_path: str) -> str:
    with open(f'./{file_path}', 'r') as fd:
        return fd.read()

def gen_password(n: int) -> str:
    # Character pools
    uppercase = secrets.choice(string.ascii_uppercase)
    lowercase = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)

    # Fill the rest of the password length
    all_chars = string.ascii_letters + string.digits
    remaining_chars = [secrets.choice(all_chars) for _ in range(n - 3)]

    # Combine and shuffle to randomize order
    password_list = [uppercase, lowercase, digit] + remaining_chars
    secrets.SystemRandom().shuffle(password_list)  # Secure shuffle

    return ''.join(password_list)

vpc = aws.ec2.Vpc(
    resource_name='poc-vpc',
    cidr_block=VPC_CIDR,
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={
        'Name': 'poc-vpc',
    }
)

public_subnet = aws.ec2.Subnet(
    resource_name='poc-public-subnet',
    vpc_id=vpc.id,
    cidr_block=PUBLIC_SUBNET_CIDR,
    map_public_ip_on_launch=True,
    availability_zone=AZ_NAME,
    tags={
        'Name': 'poc-public-subnet'
    }
)

private_subnet = aws.ec2.Subnet(
    resource_name='poc-private-subnet',
    vpc_id=vpc.id,
    cidr_block=PRIVATE_SUBNET_CIDR,
    map_public_ip_on_launch=False,
    availability_zone=AZ_NAME,
    tags={
        'Name': 'poc-private-subnet'
    }
)

internet_gateway = aws.ec2.InternetGateway(
    resource_name='poc-igw',
    vpc_id=vpc.id,
    tags={
        'Name': 'poc-igw'
    }
)

elastic_ip = aws.ec2.Eip(
    resource_name='nat-eip'
)

nat_gateway = aws.ec2.NatGateway(
    resource_name='poc-ngw',
    allocation_id=elastic_ip.id,
    subnet_id=public_subnet.id,
    tags={
        'Name': 'poc-ngw'
    }
)

public_route_table = aws.ec2.RouteTable(
    resource_name='poc-public-rt',
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block='0.0.0.0/0',
            gateway_id=internet_gateway.id
        )
    ],
    tags={
        'Name': 'poc-public-rt'
    }
)

private_route_table = aws.ec2.RouteTable(
    resource_name='poc-private-rt',
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block='0.0.0.0/0',
            nat_gateway_id=nat_gateway.id
        )
    ],
    tags={
        'Name': 'poc-private-rt'
    }
)

public_route_table_association = aws.ec2.RouteTableAssociation(
    resource_name='public-rt-association',
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id
)

private_route_table_association = aws.ec2.RouteTableAssociation(
    resource_name='private-rt-association',
    subnet_id=private_subnet.id,
    route_table_id=private_route_table.id
)

nodejs_security_group = aws.ec2.SecurityGroup(
    resource_name='nodejs-security-group',
    vpc_id=vpc.id,
    description="Security group for Node.js application",
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=['0.0.0.0/0']
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=3000,
            to_port=3000,
            cidr_blocks=['0.0.0.0/0']
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol='-1',
            from_port=0,
            to_port=0,
            cidr_blocks=['0.0.0.0/0']
        )
    ],
    tags={
        'Name': 'nodejs-security-group'
    }
)

db_security_group = aws.ec2.SecurityGroup(
    resource_name='db-security-group',
    vpc_id=vpc.id,
    description='Security group for MySQL database',
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=[public_subnet.cidr_block],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=3306,
            to_port=3306,
            cidr_blocks=[public_subnet.cidr_block, private_subnet.cidr_block]
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol='-1',
            from_port=0,
            to_port=0,
            cidr_blocks=['0.0.0.0/0']
        )
    ],
    tags={
        'Name': 'db-security-group'
    }
)

vault_security_group = aws.ec2.SecurityGroup(
    resource_name='vault-security-group',
    vpc_id=vpc.id,
    description='Security group for Vault server',
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=[public_subnet.cidr_block],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=8200,
            to_port=8200,
            cidr_blocks=[public_subnet.cidr_block]
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol='-1',
            from_port=0,
            to_port=0,
            cidr_blocks=['0.0.0.0/0']
        )
    ],
    tags={
        'Name': 'vault-security-group'
    }
)

redis_security_group = aws.ec2.SecurityGroup(
    resource_name='redis-security-group',
    vpc_id=vpc.id,
    description='Security group for Redis server',
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=22,
            to_port=22,
            cidr_blocks=[public_subnet.cidr_block],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol='tcp',
            from_port=6379,
            to_port=6379,
            cidr_blocks=[public_subnet.cidr_block, private_subnet.cidr_block]
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol='-1',
            from_port=0,
            to_port=0,
            cidr_blocks=['0.0.0.0/0']
        )
    ],
    tags={
        'Name': 'redis-security-group'
    }
)

# Create an IAM role for EC2 instances
# Specify entities that can assume this role under specified conditions.
ec2_role = aws.iam.Role("ec2_SSM_Role",
    assume_role_policy='''\
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'''
)

# Attach the AmazonSSMManagedInstanceCore policy to enable SSM
ssm_policy_attachment = aws.iam.RolePolicyAttachment("ssmPolicyAttachment",
    role=ec2_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
)

# Create a custom policy for SSM parameter operations
ssm_parameter_policy = aws.iam.Policy("ssmParameterPolicy",
    policy='''\
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:DeleteParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/*"
    }
  ]
}
'''
)

# Attach the SSM parameter policy to the role
ssm_parameter_attachment = aws.iam.RolePolicyAttachment("ssmParameterAttachment",
    role=ec2_role.name,
    policy_arn=ssm_parameter_policy.arn
)

# Create an instance profile to attach the role to EC2 instances
instance_profile = aws.iam.InstanceProfile("ec2InstanceProfile",
    role=ec2_role.name
)


redis_setup_script = read_file('scripts/redis/redis-setup.sh')

REDIS_PASSWORD = gen_password(12)

def generate_redis_user_data(redis_password):
    return f'''\
#!/usr/bin/env bash
set -ex
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
    subnet_id = private_subnet.id,
    key_name = 'master-key',
    vpc_security_group_ids=[
        redis_security_group.id
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
            nat_gateway,
            private_route_table_association,
            private_subnet
        ]
    )
)

mysql_setup_script = read_file('scripts/mysql/mysql-setup.sh')
mysql_hcheck_script = read_file('scripts/mysql/mysql-check.sh')
mysql_hcheck_service = read_file('scripts/mysql/mysql-check.service')


DB_VAULT_PASS = gen_password(12)

def generate_mysql_user_data(redis_host_ip, redis_pass, db_vault_pass, private_subnet_cidr):
    return f'''\
#!/usr/bin/env bash
set -ex
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
    subnet_id = private_subnet.id,
    key_name = 'master-key',
    vpc_security_group_ids=[
        db_security_group.id
    ],
    user_data=pulumi.Output.all(redis_ec2.private_ip, REDIS_PASSWORD, DB_VAULT_PASS, PRIVATE_SUBNET_CIDR).apply(
        lambda args: generate_mysql_user_data(*args),
    ),
    user_data_replace_on_change=True,
    tags = {
        'Name': 'db-server'
    },
    opts=pulumi.ResourceOptions(
        depends_on=[
            redis_ec2
        ]
    )
)

vault_setup_script = read_file('scripts/vault/vault-setup.sh')
vault_hcheck_script = read_file('scripts/vault/vault-check.sh')
vault_hcheck_service = read_file('scripts/vault/vault-check.service')
vault_setup_service = read_file('scripts/vault/vault-run.service')

def generate_vault_user_data(redis_host_ip, redis_pass, db_host_ip, db_user, db_pass):
    return f'''\
#!/usr/bin/env bash
set -ex
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

cat > /etc/systemd/system/vault-run.service << 'EOF'
{vault_setup_service}
EOF

cat > /usr/local/bin/vault-setup.sh << 'FINAL'
{vault_setup_script}
FINAL

chmod u+x /usr/local/bin/vault-check.sh
chmod 500 /usr/local/bin/vault-setup.sh


/usr/local/bin/vault-setup.sh

chown vault:vault /usr/local/bin/vault-check.sh
chmod 500 /usr/local/bin/vault-check.sh

systemctl enable --now vault-run.service
systemctl enable --now vault-check.service
'''

vault_ec2 = aws.ec2.Instance(
    resource_name = 'vault-server',
    instance_type = 't2.micro',
    ami = 'ami-01811d4912b4ccb26',
    iam_instance_profile=instance_profile.name,
    subnet_id = private_subnet.id,
    key_name = 'master-key',
    vpc_security_group_ids=[
        vault_security_group.id
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
        ]
    )
)

# nodejs_app_code = read_file('src/app.js')
nodejs_setup_script = read_file('scripts/app_server/nodejs-setup.sh')
nodejs_app_service = read_file('scripts/app_server/nodejs-app.service')

def generate_nodejs_user_data(redis_host_ip, db_host_ip, vault_host_ip, redis_pass):
    return f'''\
#!/usr/bin/env bash
set -ex
exec > >(tee /var/log/nodejs-userdata.log) 2>&1

echo "REDIS_HOST_IP={redis_host_ip}" >> /etc/environment
echo "REDIS_PASSWORD={redis_pass}" >> /etc/environment
echo "DB_HOST_IP={db_host_ip}" >> /etc/environment
echo "VAULT_HOST_IP={vault_host_ip}" >> /etc/environment
echo "DB_NAME={DB_NAME}" >> /etc/environment

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

/usr/local/bin/nodejs-setup.sh && \
rm /usr/local/bin/nodejs-setup.sh
'''

nodejs = aws.ec2.Instance(
    resource_name='nodejs-server',
    instance_type='t2.micro',
    ami='ami-01811d4912b4ccb26',
    iam_instance_profile=instance_profile.name,
    subnet_id=public_subnet.id,
    key_name='master-key',
    vpc_security_group_ids=[
        nodejs_security_group.id
    ],
    associate_public_ip_address=True,
    user_data=pulumi.Output.all(redis_ec2.private_ip, db.private_ip, vault_ec2.private_ip, REDIS_PASSWORD).apply(
        lambda args: generate_nodejs_user_data(*args)
    ),
    user_data_replace_on_change=True,
    tags={
        'Name': 'nodejs-server'
    }
)

all_ips = [nodejs.public_ip, db.private_ip, redis_ec2.private_ip, vault_ec2.private_ip]

def create_config_file(all_ips):
    config_content = f'''\
Host nodejs-server
    HostName {all_ips[0]}
    User ubuntu
    IdentityFile ~/.ssh/master-key.id_rsa

Host db-server
    ProxyJump nodejs-server
    HostName {all_ips[1]}
    User ubuntu
    IdentityFile ~/.ssh/master-key.id_rsa

Host redis-server
    ProxyJump nodejs-server
    HostName {all_ips[2]}
    User ubuntu
    IdentityFile ~/.ssh/master-key.id_rsa

Host vault-server
    ProxyJump nodejs-server
    HostName {all_ips[3]}
    User ubuntu
    IdentityFile ~/.ssh/master-key.id_rsa
'''
    config_path = os.path.expanduser("~/.ssh/config")
    with open(config_path, "w") as config_file:
        config_file.write(config_content)

pulumi.Output.all(*all_ips).apply(create_config_file)

pulumi.export('NodeJS Public IP', nodejs.public_ip)
