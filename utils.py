import pulumi
import pulumi_aws as aws
import pulumi_tls as tls
import os
import secrets
import string

def read_file(file_path: str) -> str:
    """Read and return the contents of a file"""
    with open(f'./{file_path}', 'r') as fd:
        return fd.read()

def gen_password(n: int) -> str:
    """Generate a secure random password of length n"""
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

def create_ssh_key(key_name):
    """Create or use an existing SSH key pair"""
    try:
        existing_key = aws.ec2.get_key_pair(key_name=key_name)
        print(f"Using existing AWS key pair: {existing_key.key_name}")
        return None  # Use existing key

    except:
        print(f"Key pair '{key_name}' not found. Creating a new one...")

        ssh_key = tls.PrivateKey(
            key_name,
            algorithm="RSA",
            rsa_bits=4096,
        )

        aws_key = aws.ec2.KeyPair(
            key_name,
            key_name=key_name,
            public_key=ssh_key.public_key_openssh
        )

        # Save private key locally
        private_key_path = os.path.expanduser(f"~/.ssh/{key_name}.id_rsa")

        def write_private_key(private_key_pem):
            with open(private_key_path, "w") as private_key_file:
                private_key_file.write(private_key_pem)
            os.chmod(private_key_path, 0o600)

        ssh_key.private_key_pem.apply(write_private_key)

        return aws_key

def create_config_file(instances, ssh_key_name):
    """Create SSH config file for connecting to instances"""
    def write_config(all_ips):
        nodejs_ip = all_ips[0]
        db_ip = all_ips[1]
        redis_ip = all_ips[2]
        vault_ip = all_ips[3]

        config_content = f'''\
Host nodejs-server
    HostName {nodejs_ip}
    User ubuntu
    IdentityFile ~/.ssh/{ssh_key_name}.id_rsa

Host db-server
    ProxyJump nodejs-server
    HostName {db_ip}
    User ubuntu
    IdentityFile ~/.ssh/{ssh_key_name}.id_rsa

Host redis-server
    ProxyJump nodejs-server
    HostName {redis_ip}
    User ubuntu
    IdentityFile ~/.ssh/{ssh_key_name}.id_rsa

Host vault-server
    ProxyJump nodejs-server
    HostName {vault_ip}
    User ubuntu
    IdentityFile ~/.ssh/{ssh_key_name}.id_rsa
'''
        config_path = os.path.expanduser("~/.ssh/config")
        with open(config_path, "w") as config_file:
            config_file.write(config_content)

    pulumi.Output.all(
        instances["nodejs"].public_ip,
        instances["db"].private_ip,
        instances["redis"].private_ip,
        instances["vault"].private_ip
    ).apply(write_config)