import pulumi
import pulumi_aws as aws

def create_security_groups(vpc, public_subnet, private_subnet):
    """Create security groups for each component"""

    # Node.js application security group
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
        tags={'Name': 'nodejs-security-group'}
    )

    # Database security group
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
        tags={'Name': 'db-security-group'}
    )

    # Vault security group
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
        tags={'Name': 'vault-security-group'}
    )

    # Redis security group
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
        tags={'Name': 'redis-security-group'}
    )

    return {
        "nodejs": nodejs_security_group,
        "db": db_security_group,
        "vault": vault_security_group,
        "redis": redis_security_group
    }

def create_iam_resources():
    """Create IAM roles and policies for EC2 instances"""

    # Create IAM role for EC2 instances
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

    return {
        "role": ec2_role,
        "instance_profile": instance_profile
    }