#!/bin/bash -xe
set -xuo pipefail

# Patch host and install Docker
yum update -y
amazon-linux-extras install docker
systemctl start docker
systemctl enable docker

mkdir /home/ec2-user/gophish

# Generate a self signed cert
openssl req -x509 -newkey rsa:4096 -keyout /home/ec2-user/gophish/gophish_admin.key -out /home/ec2-user/gophish/gophish_admin.crt -sha256 -days 365 -nodes -subj "/C=US/"

# Configure gophish settings
cat > /home/ec2-user/gophish/config.json << EOF
{
  "admin_server": {
    "listen_url": "0.0.0.0:8080",
    "use_tls": true,
    "cert_path": "gophish_admin.crt",
    "key_path": "gophish_admin.key"
  },
  "phish_server": {
    "listen_url": "0.0.0.0:80",
    "use_tls": false,
    "cert_path": "example.crt",
    "key_path": "example.key"
  },
  "db_name": "sqlite3",
  "db_path": "gophish.db",
  "migrations_prefix": "db/db_",
  "contact_address": "",
  "logging": {
    "filename": "",
    "level": ""
  }
}
EOF

touch /home/ec2-user/gophish/gophish.db
chmod 666 /home/ec2-user/gophish/*

docker pull gophish/gophish:latest
docker run -d \
  -p 8080:8080 \
  -p 80:80 \
  -e GOPHISH_INITIAL_ADMIN_PASSWORD=${InitialAdminPassword} \
  -v /home/ec2-user/gophish/config.json:/opt/gophish/config.json \
  -v /home/ec2-user/gophish/gophish.db:/opt/gophish/gophish.db \
    gophish/gophish:latest

/opt/aws/bin/cfn-signal --success true \
  --resource ASGGophish \
  --stack ${AWS::StackName} \
  --region ${AWS::Region}
