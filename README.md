# Gophish Cloudformation Deployment

## Architecture
* A Route 53 `Hosted Zone` is created for each phishing domain
* An `Amazon Certificate Manager` SSL cert is provisioned and verified for each Domain using Route 53
* DNS records point to an `Application Load Balancer` with all `ACM` Certs attached
* The `ALB` forwards traffic to an Autoscaling group with one `EC2` instance running Gophish

## Requirements
* [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* [jq](https://stedolan.github.io/jq/download/)
* python 3.10
* pipenv

## Deployment Steps

1. Clone this repo

2. Edit `config.yaml` with your preferences

3. Deploy hosted zones for each phishing domain:
```
./manage.sh update_zones
```

4. Update NS records for each domain to the nameservers listed in script output
Example:
```
Domain: phish.com
        ns-219.awsdns-27.com
        ns-1365.awsdns-42.org
        ns-797.awsdns-35.net
        ns-1828.awsdns-36.co.uk
```

5. Once the records have propogated, build and deploy the Gophish stack:
```
./manage.sh update_platform
```
