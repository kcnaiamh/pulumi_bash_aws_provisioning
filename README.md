## Project Overview

This project automates the provisioning of a secure AWS infrastructure using Pulumi with Python and integrates multiple components such as:

- **Dynamic secrets management** with HashiCorp Vault.
- **Database provisioning and configuration** using MySQL.
- **Health monitoring** via Redis.
- **Deployment** of a Node.js application.
- **Automated setup and configuration** via bash scripts.

The primary goal is to create a robust, automated, and secure deployment solution that minimizes manual intervention and enforces best practices with security in mind.

## Architecture

This is the top level overview of the whole infrastructure that the code will build.

![](https://github.com/user-attachments/assets/6547346d-1ee6-4a78-8a85-37864c8d0d6b)

## Technologies Used

- **Programming & Scripting Languages:**

  - Python (Pulumi scripts)
  - Bash (Setup and configuration scripts)
  - Node.js (Application code)

- **Infrastructure & Cloud Services:**

  - Pulumi with the `pulumi-aws`, `pulumi-tls` provider
  - Amazon Web Services (AWS): EC2, VPC, Subnets, NAT Gateway, Internet Gateway, IAM, SSM, etc.

- **Databases & Data Stores:**

  - MySQL (Database server)
  - Redis (Health monitoring via pub/sub)

- **Security & Secrets Management:**

  - **HashiCorp Vault** (Dynamic generation of temporary database credentials)

- **System & Service Management:**

  - Systemd (Service unit files for managing Node.js, MySQL, and Vault services)

- **Additional Tools & Utilities:**

  - AWS CLI (Communicate with AWS components through bash scripts)
  - Git (Cloning Node.js application repository)
  - npm (For Node.js package installation)
  - Command-line utilities: `curl`, `wget`, `unzip`, `jq`, `gpg`, `lsb-release`, `netcat-openbsd`, etc.

## Prerequisites

Before running the project, ensure you have:

- **Linux** host machine (or VM) running.
- **AWS Account** with proper permissions and balance.
- **Pulumi CLI** installed and configured.
- **AWS CLI** installed and configured.

For setting up AWS & Pulumi CLI, you can [follow this blog](https://blog.kcnaiamh.com/installing-and-setting-up-aws-cli-and-pulumi-on-ubuntu-2404).

## Deployment & Execution

**Attention**: Make sure you have all the prerequisites mentioned previously before proceeding for deployment.

To deploy the infrastructure and services you just need to run 2 commands.

1. **Use The Template**
   Yes, this repo is actually a Pulumi template. You can directly setup you project just running the following command in an **empty directory**.

   ```
   pulumi new https://github.com/kcnaiamh/pulumi_bash_aws_provisioning
   ```

2. **Run Pulumi Up**
   This command will provision the AWS resources as defined in `__main__.py`.

   ```
   pulumi up --yes
   ```

It will take 3/4 minute for provisioning the AWS infrastructure. But that doesn't mean you can use the webapp immediately. Cause the bash scripts runed inside EC2 instances will take time to finish execution.

Wail for 10-15 minutes. Then type `http://<your_nodejs_app_public_ip>:3000` in your browser to see the webapp.

## Security Considerations

- **Dynamic Credential Generation:**
  Vault dynamically generates temporary database credentials. **Keep Vault keys secure and never expose them publicly.** Avoid logging credentials to log files—though, in this project, I have logged them for debugging purposes.

- **Access Control:**
  AWS IAM roles and security groups are configured to restrict access to resources. **Ensure that security groups and IAM policies follow the principle of least privilege** to minimize exposure.

- **Sensitive Data:**
  Environment variables and configuration files may contain sensitive data such as database passwords and API tokens. **Secure these files and manage permissions carefully.** Keep in mind that, by default, any user can read the `/etc/environment` file, so avoid storing sensitive credentials there. Even if you use if for automation, remove it in the process of last clean-up process in automation script (advice to me :)).

- **Service Hardening:**
  Systemd services are configured to automatically restart upon failure, ensuring service continuity. **Use the least privilege principle for sensitive files, especially scripts executed by systemd or cron jobs running as a privileged user.** Regularly update and patch all installed packages. Additionally, note that the default user in an EC2 instance can use the `sudo` binary without a password. **For added security, consider enforcing password authentication for sudo access.**

- **Communication Security:**
  Always use secure communication channels such as HTTPS and SSH where possible. **Avoid exposing sensitive ports to the public internet.** In this project, TLS has been disabled in Vault to simplify the setup by avoiding certificate installation. Similarly, the Node.js server is not configured with a TLS certificate for HTTPS.

## Troubleshooting & Maintenance

- **Pulumi Deployment Issues:**

  - Check Pulumi logs for errors.
  - Ensure that AWS credentials and configurations are correct.

- **Service Failures:**

  - Use `systemctl status <service-name>` to view the status and logs of Node.js, MySQL, or Vault services.
  - Check log files under `/var/log/` on the affected EC2 instance.

- **Script Failures:**
  - Examine log outputs (e.g., `/var/log/mysql-setup.log`, `/var/log/redis-setup.log`) for error messages.
  - Validate that all required environment variables are properly set.

## Challenges and Solutions

During the automation process, I encountered several challenges. In this section, I'll highlight the most significant ones and how I resolved them.

1. **Connecting Components**
   Connecting multiple components was one of the most challenging parts. Debugging issues became time-consuming when too many things were running at once. To tackle this, I broke down the setup into smaller components. I spun up multiple VMs separately and manually established connections between them. This approach helped me understand what worked, what didn’t, and how to automate the process reliably.

2. **Circular Dependency**
   To secure the database connection, I configured Vault to generate dynamic credentials only from a specific IP—its own. However, this created a circular dependency:

   - The MySQL EC2 instance needed to be running before Vault, as Vault’s setup script required a working database connection.
   - At the same time, the MySQL setup script required Vault’s EC2 IP to execute certain MySQL commands.

   To resolve this, I temporarily relaxed the security restrictions by allowing the entire `/24` CIDR range of the private subnet instead of just Vault’s IP. This ensured both instances could complete their setup without manual intervention.

3. **Logging**
   Debugging automation failures is crucial, especially when scripts crash. To improve visibility, I enabled detailed logging in every Bash script by using:

   ```bash
   exec > >(tee -a /var/log/logfile.log) 2>&1
   set -euxo pipefail
   ```

   This setup ensures that:

   - Every command and its output are logged to `/var/log/logfile.log`.
   - Errors cause immediate script termination (`set -e`).
   - Undefined variables trigger an error (`set -u`).
   - Pipelines fail if any command within them fails (`set -o pipefail`).

## Conclusion

This project provides an end-to-end solution for automated, secure AWS infrastructure provisioning with dynamic secrets management, centralized health monitoring, and application deployment from Github. By leveraging Pulumi, AWS, Vault, MySQL, Redis, and Node.js, it addresses common challenges in modern cloud deployments and ensures a resilient, secure environment.
