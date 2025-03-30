## Efficient AWS Infrastructure Provisioning with Pulumi: Automate Node.js Application Deployment with Systemd Service Chaining and MySQL Healthcheck

![diagram-export-3-3-2025-8_40_44-PM](https://github.com/user-attachments/assets/1fc44d33-30b1-43f8-bc4e-0d6b9f8427ef)

Lets spin up a fresh Linux VM and run the following command to make the environment ready.

```
sudo apt update
```

```
sudo apt install -y unzip
sudo apt install -y python3.12-venv
```

---

Now install AWS CLI: ([source](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))

```
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" 2>/dev/null
unzip awscliv2.zip
sudo ./aws/install
```

Configure AWS CLI by running the following command and giving appropriate credentials.

```
aws configure
```

> [!Todo]
> Log into your AWS account and get the access key. Then export it.

---

Now install Pulumi: ([source](https://www.pulumi.com/docs/iac/download-install/))

```
curl -fsSL https://get.pulumi.com | sh
```

```
bash
```

Authenticate your pulumi account with temporary token

```
pulumi login
```

```
mkdir -p ~/kc-service-infra
cd ~/kc-service-infra
```

Create a new pulumi project

```
pulumi new
```

Now select `aws-python` template

---

Create an AWS Key Pair

```shell
cd ~/.ssh/
aws ec2 create-key-pair --key-name master-key --output text --query 'KeyMaterial' > master-key.id_rsa
chmod 400 master-key.id_rsa
```

This will save the private key as `master-key.id_rsa` in the `~/.ssh/` directory and restrict its permissions.

---

Write your infrastructure provisioning code in `__main__.py` file.

Now provision the infrastructure

```
pulumi up --yes
```

---

As we have already created the config file, we can SSH into the DB server through the Node.js server:

```
ssh db-server
```

Change the hostname of the DB server to `db-server` to make it easier to identify.

```
sudo hostnamectl set-hostname db-server
```

---

We can see that the Node.js application is running on port 3000. We can access it from anywhere using the public IP of the Node.js server.

```
curl http://<PUBLIC IP>:3000
```

---

Destroy all resources

```
pulumi destroy --yes
```

Delete stack

```
pulumi stack rm
```

---

**Problem With This Design**

1. Only checks if MySQL is up and running before starting NodeJS application. Not when application is running.
   So, if MySQL crashes or if not unreachable, NodeJS application will not work properly.
2. MySQL availability is checked from NodeJS EC2 by probing to MySQL default port.
   If the default port required to changed in future 'check-mysql.sh' file need to be updated in NodeJS EC2.
   In case of firewall block the connection, NodeJS application will not start.
3. For each Application server which depends on MySQL will need to have 'check-mysql.sh' file.
4. No centralized monitoring for healthcheck data of all the services.
