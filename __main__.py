import pulumi
from network import create_network_infrastructure
from security import create_security_groups, create_iam_resources
from instances import create_instances
from utils import create_ssh_key, create_config_file

# Configuration
config = pulumi.Config()
DB_NAME = config.require("dbName")
DB_VAULT_USER = config.require("dbVaultUser")
SSH_KEY_NAME = config.require("sshKeyName")

# Create infrastructure components
aws_key = create_ssh_key(SSH_KEY_NAME)

network = create_network_infrastructure()
vpc = network["vpc"]
public_subnet = network["public_subnet"]
private_subnet = network["private_subnet"]

security = create_security_groups(vpc, public_subnet, private_subnet)
iam_resources = create_iam_resources()

instances = create_instances(
    network=network,
    security_groups=security,
    iam_profile=iam_resources["instance_profile"],
    config={
        "db_name": DB_NAME,
        "db_vault_user": DB_VAULT_USER,
        "ssh_key_name": SSH_KEY_NAME,
        "aws_key": aws_key
    }
)

# Export results
create_config_file(instances, SSH_KEY_NAME)
pulumi.export('NodeJS Running On http://public_ip:3000', instances['nodejs'].public_ip)