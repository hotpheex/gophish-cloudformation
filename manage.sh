#!/bin/bash

validate_requirements() {
    command -v aws >/dev/null 2>&1 || { echo >&2 "Script requires aws CLI (https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)"; exit 1; }
    command -v jq >/dev/null 2>&1 || { echo >&2 "Script requires jq (https://stedolan.github.io/jq/download/)"; exit 1; }
    command -v pipenv run sceptre >/dev/null 2>&1 || { echo >&2 "Run 'pipenv install'"; exit 1; }
}

get_nameservers() {
    hosted_zone_ids=$(aws cloudformation --region ap-southeast-2 describe-stacks --stack-name gophish-hosted-zones-stack --query 'Stacks[0].Outputs[].OutputValue' | jq -r '.[]')

    printf "\nSet the following DNS nameservers for each domain:\n"
    printf '=%.0s' {1..50}

    for zone_id in ${hosted_zone_ids}; do
        hostedzone_data=$(aws route53 get-hosted-zone --id "${zone_id}")
        domain=$(echo "${hostedzone_data}" | jq -r ".HostedZone.Name")
        declare -a nameservers=($(echo "${hostedzone_data}" | jq -r ".DelegationSet.NameServers[]"))

        printf "\nDomain: ${domain}\n"
        for ns in "${nameservers[@]}"; do
            printf "\t${ns}\n"
        done
    done
    printf '=%.0s' {1..50}
}

print_instance_ip() {
    instance_metadata=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=Gophish (gophish-platform-stack)" "Name=instance-state-name,Values=running")
    ip=$(echo "${instance_metadata}" | jq -r '.Reservations[] | .Instances[] | .PublicIpAddress')

    printf "\nInstance IP: ${ip}\n"
}

parse_arguments() {
    CMD="${1}"

    case ${CMD} in
    "update_zones")
        pipenv run sceptre --var-file config.yaml launch hosted-zones -y
        get_nameservers
        ;;
    "update_platform")
        pipenv run sceptre --var-file config.yaml launch platform -y
        echo "Waiting 30sec for instance to start..."; sleep 30
        print_instance_ip
        ;;
    *)
        echo """ERROR: Please provide a valid command. Usage:
    ./manage.sh
        update_zones
        update_platform
    """
        exit 99
        ;;
    esac
}

validate_requirements
parse_arguments "$@"
