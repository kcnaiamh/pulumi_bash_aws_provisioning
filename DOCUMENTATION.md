# Comprehensive Documentation

## Overview

This Pulumi project provisions a secure AWS infrastructure on Linux using Pulumi (Python). It automates the deployment of a NodeJS application with MySQL, Vault, and Redis. The codebase includes infrastructure provisioning, security group configurations, IAM role assignments, EC2 instance creation, and initialization scripts for each component.

## Detailed File Descriptions

### Infrastructure Orchestration

- **[**main**.py](**main**.py)**
  This is the entry point for the Pulumi deployment. It:

  - Loads configuration values (database name, Vault user, SSH key name).
  - Creates network resources via [`network.create_network_infrastructure`](network.py).
  - Sets up security groups and IAM resources using [`security.create_security_groups`](security.py) and [`security.create_iam_resources`](security.py).
  - Provisions EC2 instances by calling [`instances.create_instances`](instances.py).
  - Generates an SSH configuration file with [`utils.create_config_file`](utils.py).
  - Exports key outputs (for example, the public IP for the NodeJS server).

- **[Pulumi.yaml](Pulumi.yaml)**
  Defines project metadata, runtime configurations, and default configuration values for the AWS region, database name, Vault user, and SSH key.

### Infrastructure Components

- **[network.py](network.py)**
  Implements the network infrastructure:

  - Creates the VPC, public and private subnets.
  - Sets up the Internet Gateway and NAT Gateway.
  - Configures route tables and associations for the subnets.

- **[security.py](security.py)**
  Manages security and IAM resources:

  - Defines security groups for NodeJS, MySQL (DB), Vault, and Redis.
  - Sets inbound and outbound rules specific to each component.
  - Creates an IAM role (with SSM permissions) for EC2 instances and attaches a custom policy for SSM parameter operations.

- **[instances.py](instances.py)**
  Provisions EC2 instances for:

  - Redis: Initialized with a shell script to configure and secure Redis.
  - MySQL (DB): Uses a user-data script to install and configure MySQL, applying a healthcheck, and sets credentials based on dynamic password generation.
  - Vault: Installs, initializes, and unseals Vault as well as configures database secrets.
  - NodeJS: Boots up the NodeJS application with a systemd service and proper environment configuration.

  Each instance uses Pulumi’s dynamic generation of user-data scripts to bootstrap the necessary services.

### Utility Functions

- **[utils.py](utils.py)**
  Contain helper functions:
  - `read_file`: Reads the contents of a given file.
  - `gen_password`: Generates a secure random password.
  - `create_ssh_key`: Creates or reuses an existing SSH key pair and saves the private key locally.
  - `create_config_file`: Writes a local SSH configuration file to simplify SSH access to the provisioned instances.

### Scripts

The `scripts/` directory includes subdirectories for each component. Each component contains:

- **App Server**

  - **[scripts/app_server/nodejs-setup.sh](scripts/app_server/nodejs-setup.sh)**
    Sets up the NodeJS environment including installing Node.js, obtaining AWS SSM parameters, cloning the demo application, installing dependencies, and configuring environment variables.

  - **[scripts/app_server/nodejs-app.service](scripts/app_server/nodejs-app.service)**
    A systemd unit file that manages the NodeJS application process ensuring automatic restarts and proper logging.

- **MySQL**

  - **[scripts/mysql/mysql-setup.sh](scripts/mysql/mysql-setup.sh)**
    Installs MySQL, configures it for remote access, sets database credentials, secures installation, creates the Vault user and applies schema definitions.

  - **[scripts/mysql/mysql-check.sh](scripts/mysql/mysql-check.sh)**
    A monitoring script that periodically checks the MySQL service and publishes its status to Redis.

  - **[scripts/mysql/mysql-check.service](scripts/mysql/mysql-check.service)**
    A systemd unit file that ensures the MySQL healthcheck script runs continuously.

  - **[scripts/mysql/schema.sql](scripts/mysql/schema.sql)**
    Contains SQL commands to create the necessary database schema.

- **Redis**

  - **[scripts/redis/redis-setup.sh](scripts/redis/redis-setup.sh)**
    Installs and configures Redis, sets security and performance settings, and starts the Redis service.

- **Vault**

  - **[scripts/vault/vault-setup.sh](scripts/vault/vault-setup.sh)**
    Handles the installation, initialization, and unsealing of Vault. It also configures database connections and AppRole authentication.

  - **[scripts/vault/vault-check.sh](scripts/vault/vault-check.sh)**
    Monitors Vault’s status and publishes its health to Redis.

  - **[scripts/vault/vault-run.service](scripts/vault/vault-run.service)**
    A systemd unit file to automatically unseal Vault on failures.

  - **[scripts/vault/vault-check.service](scripts/vault/vault-check.service)**
    Ensures continuous execution of the Vault healthcheck process.

## Deployment Workflow

1. **Pre-requisites**

   Install necessary tools (Python, AWS CLI, Pulumi) as described in [README.md](README.md).

2. **Configuration**

   Update configuration parameters in [Pulumi.yaml](Pulumi.yaml) and the Pulumi configuration (e.g., via `pulumi config set ...`).

3. **Deployment**

   Run `pulumi up --yes` to deploy the infrastructure.

4. **Accessing the Application**

   The NodeJS application’s public IP is exported at the end of [**main**.py](__main__.py) and can be accessed on port 3000.

5. **Teardown**

   Use `pulumi destroy --yes` to remove all resources when done.

## Additional Information

- **Security Considerations:**
  Each component is deployed into appropriate subnets (public vs. private), and security groups are tightly controlled with ingress and egress rules.
- **Monitoring and Healthchecks:**
  Custom healthcheck scripts for MySQL and Vault publish status updates to Redis to aid in centralized monitoring.
- **SSH Access:**
  A dynamic SSH configuration is generated by [`utils.create_config_file`](utils.py) to simplify connection through a jump-host setup (using the NodeJS server as a proxy).

This documentation provides an end-to-end explanation of the codebase, file purposes, and how the various components interact to create a resilient, secure AWS infrastructure deployment.
