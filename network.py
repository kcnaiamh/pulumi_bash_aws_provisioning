import pulumi
import pulumi_aws as aws

def create_network_infrastructure():
    """Create VPC, subnets, gateways and route tables"""

    VPC_CIDR = '10.0.0.0/16'
    PRIVATE_SUBNET_CIDR = '10.0.2.0/24'
    PUBLIC_SUBNET_CIDR = '10.0.1.0/24'
    AZ_NAME = aws.get_availability_zones(state="available").names[0]

    # Create VPC
    vpc = aws.ec2.Vpc(
        resource_name='poc-vpc',
        cidr_block=VPC_CIDR,
        enable_dns_support=True,
        enable_dns_hostnames=True,
        tags={'Name': 'poc-vpc'}
    )

    # Create public subnet
    public_subnet = aws.ec2.Subnet(
        resource_name='poc-public-subnet',
        vpc_id=vpc.id,
        cidr_block=PUBLIC_SUBNET_CIDR,
        map_public_ip_on_launch=True,
        availability_zone=AZ_NAME,
        tags={'Name': 'poc-public-subnet'}
    )

    # Create private subnet
    private_subnet = aws.ec2.Subnet(
        resource_name='poc-private-subnet',
        vpc_id=vpc.id,
        cidr_block=PRIVATE_SUBNET_CIDR,
        map_public_ip_on_launch=False,
        availability_zone=AZ_NAME,
        tags={'Name': 'poc-private-subnet'}
    )

    # Create internet gateway
    internet_gateway = aws.ec2.InternetGateway(
        resource_name='poc-igw',
        vpc_id=vpc.id,
        tags={'Name': 'poc-igw'}
    )

    # Create NAT gateway for private subnet internet access
    elastic_ip = aws.ec2.Eip(resource_name='nat-eip')

    nat_gateway = aws.ec2.NatGateway(
        resource_name='poc-ngw',
        allocation_id=elastic_ip.id,
        subnet_id=public_subnet.id,
        tags={'Name': 'poc-ngw'}
    )

    # Create route tables
    public_route_table = aws.ec2.RouteTable(
        resource_name='poc-public-rt',
        vpc_id=vpc.id,
        routes=[
            aws.ec2.RouteTableRouteArgs(
                cidr_block='0.0.0.0/0',
                gateway_id=internet_gateway.id
            )
        ],
        tags={'Name': 'poc-public-rt'}
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
        tags={'Name': 'poc-private-rt'}
    )

    # Associate route tables with subnets
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

    return {
        "vpc": vpc,
        "public_subnet": public_subnet,
        "private_subnet": private_subnet,
        "nat_gateway": nat_gateway,
        "private_route_table_association": private_route_table_association
    }