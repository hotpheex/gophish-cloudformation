from troposphere import Base64, GetAtt, ImportValue, Parameter, Ref, Sub, Tags, Template
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration
from troposphere.autoscaling import Tags as AsTags
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.ec2 import SecurityGroup
from troposphere.elasticloadbalancingv2 import Action
from troposphere.elasticloadbalancingv2 import Certificate as LbCertificate
from troposphere.elasticloadbalancingv2 import (
    Listener,
    ListenerCertificate,
    LoadBalancer,
    Matcher,
    RedirectConfig,
    TargetGroup,
)
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere.route53 import AliasTarget, RecordSet, RecordSetGroup


def sceptre_handler(sceptre_user_data):
    t = Template()

    t.set_version("2010-09-09")

    t.set_description("""Gophish Phishing EC2 & Cloudfront with TLS""")

    VpcId = t.add_parameter(
        Parameter(
            "VpcId",
            Description="VPC to deploy template in",
            Type="AWS::EC2::VPC::Id",
            ConstraintDescription="Must be the ID of an existing VPC.",
        )
    )

    VpcSubnets = t.add_parameter(
        Parameter(
            "VpcSubnets",
            Description="VPC Workload Subnets to deploy instance in",
            Type="List<AWS::EC2::Subnet::Id>",
        )
    )

    InitialAdminPassword = t.add_parameter(
        Parameter(
            "InitialAdminPassword",
            Description="Initial admin console password",
            Type="String",
            NoEcho=True,
        )
    )

    AdminPort = t.add_parameter(
        Parameter(
            "AdminPort",
            Description="Admin Console Port",
            Type="Number",
        )
    )

    InstanceType = t.add_parameter(
        Parameter(
            "InstanceType",
            Description="EC2 instance Type",
            Type="String",
        )
    )

    ImageId = t.add_parameter(
        Parameter(
            "ImageId",
            Description="AMI image to create FromPort",
            Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
            Default="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2",
        )
    )

    Ec2Keyname = t.add_parameter(
        Parameter(
            "Ec2Keyname",
            Description="EC2 SSH Key Pair",
            Type="AWS::EC2::KeyPair::KeyName",
        )
    )

    ClusterMaxSize = t.add_parameter(
        Parameter(
            "ClusterMaxSize",
            Description="Maximum Cluster size of Web Server instances",
            Type="String",
            Default="2",
        )
    )

    ClusterMinSize = t.add_parameter(
        Parameter(
            "ClusterMinSize",
            Description="Minimum Cluster size of Web Server instances",
            Type="String",
            Default="1",
        )
    )

    ClusterDesiredSize = t.add_parameter(
        Parameter(
            "ClusterDesiredSize",
            Description="Minimum Cluster size of Web Server instances",
            Type="String",
            Default="1",
        )
    )

    GracePeriod = t.add_parameter(
        Parameter(
            "GracePeriod",
            Description="Autoscaling Grace period",
            Type="String",
            Default="300",
        )
    )

    # Resources
    ec2_ingress_rules = [
        {
            "FromPort": 80,
            "ToPort": 80,
            "IpProtocol": "tcp",
            "Description": "Landing page web traffic",
            "SourceSecurityGroupId": Ref("SGAlb"),
        },
    ]
    for cidr in sceptre_user_data["ingressRules"]["adminConsole"]:
        ec2_ingress_rules.append(
            {
                "CidrIp": cidr,
                "FromPort": 22,
                "ToPort": 22,
                "IpProtocol": "tcp",
                "Description": f"SSH from {cidr}",
            }
        )
        ec2_ingress_rules.append(
            {
                "CidrIp": cidr,
                "FromPort": 8080,
                "ToPort": 8080,
                "IpProtocol": "tcp",
                "Description": f"Admin Console from {cidr}",
            }
        )

    SGGophish = t.add_resource(
        SecurityGroup(
            "SGGophish",
            GroupDescription="Security Group for EC2 Instance",
            VpcId=Ref(VpcId),
            SecurityGroupIngress=ec2_ingress_rules,
        )
    )

    alb_ingress_rules = []
    for cidr in sceptre_user_data["ingressRules"]["landingPages"]:
        alb_ingress_rules.append(
            {
                "CidrIp": cidr,
                "FromPort": 80,
                "ToPort": 80,
                "IpProtocol": "tcp",
                "Description": f"HTTP Port from {cidr}",
            }
        )
        alb_ingress_rules.append(
            {
                "CidrIp": cidr,
                "FromPort": 443,
                "ToPort": 443,
                "IpProtocol": "tcp",
                "Description": f"HTTPS Port from {cidr}",
            },
        )

    SGAlb = t.add_resource(
        SecurityGroup(
            "SGAlb",
            GroupDescription="Security Group for Application LoadBalancer",
            VpcId=Ref(VpcId),
            SecurityGroupIngress=alb_ingress_rules,
        )
    )

    ALBGophish = t.add_resource(
        LoadBalancer(
            "ALBGophish",
            Name=Sub("${AWS::StackName}-ALB"),
            Scheme="internet-facing",
            Subnets=Ref(VpcSubnets),
            SecurityGroups=[Ref("SGAlb")],
            Tags=Tags(PublicResource="Yes"),
        )
    )

    ALBListenerHttp = t.add_resource(
        Listener(
            "ALBListenerHttp",
            LoadBalancerArn=Ref("ALBGophish"),
            Port=80,
            Protocol="HTTP",
            DefaultActions=[
                Action(
                    Type="redirect",
                    Order=1,
                    RedirectConfig=RedirectConfig(
                        Protocol="HTTPS",
                        Host="#{host}",
                        Query="#{query}",
                        Path="/#{path}",
                        Port="443",
                        StatusCode="HTTP_301",
                    ),
                )
            ],
        )
    )

    ALBListenerHttps = t.add_resource(
        Listener(
            "ALBListenerHttps",
            Certificates=[LbCertificate(CertificateArn=Ref("ACMAlbCertificate0"))],
            LoadBalancerArn=Ref("ALBGophish"),
            Port=443,
            Protocol="HTTPS",
            DefaultActions=[
                Action(Type="forward", TargetGroupArn=Ref("TGGophishLanding"))
            ],
        )
    )

    TGGophishLanding = t.add_resource(
        TargetGroup(
            "TGGophishLanding",
            VpcId=Ref("VpcId"),
            Protocol="HTTP",
            Port=80,
            TargetType="instance",
            HealthCheckProtocol="HTTP",
            HealthCheckPath="/",
            HealthCheckTimeoutSeconds=5,
            HealthCheckIntervalSeconds=30,
            HealthyThresholdCount=2,
            Matcher=Matcher(HttpCode="200,404"),
            UnhealthyThresholdCount=3,
        )
    )

    EC2InstanceRole = t.add_resource(
        Role(
            "EC2InstanceRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            Policies=[
                Policy(
                    PolicyName=Sub("${AWS::StackName}-Gophish-Policy"),
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "SecurityGroupDiscovery",
                                "Action": [
                                    "ec2:DescribeInstances",
                                    "ec2:DescribeSecurityGroups",
                                ],
                                "Effect": "Allow",
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
        )
    )

    EC2InstanceProfile = t.add_resource(
        InstanceProfile(
            "EC2InstanceProfile",
            Path="/basic/",
            Roles=[Ref("EC2InstanceRole")],
        )
    )

    ASGGophish = t.add_resource(
        AutoScalingGroup(
            "ASGGophish",
            Cooldown=Ref("GracePeriod"),
            LaunchConfigurationName=Ref("LCGophish"),
            MinSize=Ref("ClusterMinSize"),
            MaxSize=Ref("ClusterMaxSize"),
            DesiredCapacity=Ref("ClusterDesiredSize"),
            HealthCheckGracePeriod=Ref("GracePeriod"),
            HealthCheckType="EC2",
            Tags=AsTags(
                Name=Sub("Gophish (${AWS::StackName})"),
            ),
            TargetGroupARNs=[Ref("TGGophishLanding")],
            TerminationPolicies=["OldestInstance", "Default"],
            VPCZoneIdentifier=Ref("VpcSubnets"),
        )
    )

    LCGophish = t.add_resource(
        LaunchConfiguration(
            "LCGophish",
            IamInstanceProfile=Ref("EC2InstanceProfile"),
            InstanceType=Ref("InstanceType"),
            ImageId=Ref("ImageId"),
            KeyName=Ref("Ec2Keyname"),
            SecurityGroups=[Ref("SGGophish")],
            UserData=Base64(Sub(sceptre_user_data["ec2UserData"])),
        )
    )

    # Dynamic resources per domain name
    certs = {}
    for index in range(len(sceptre_user_data["domains"])):
        domain_name = sceptre_user_data["domains"][index]
        hosted_zone_id = ImportValue(f"GophishHostedZoneId{index}")

        certs[index] = t.add_resource(
            Certificate(
                f"ACMAlbCertificate{index}",
                DomainName=domain_name,
                ValidationMethod="DNS",
                DomainValidationOptions=[
                    DomainValidationOption(
                        DomainName=domain_name,
                        HostedZoneId=hosted_zone_id,
                    ),
                    DomainValidationOption(
                        DomainName=f"www.{domain_name}",
                        HostedZoneId=hosted_zone_id,
                    ),
                ],
                SubjectAlternativeNames=[f"www.{domain_name}"],
            )
        )

        if index > 0:
            t.add_resource(
                ListenerCertificate(
                    f"ALBAlbListenerCertificate{index}",
                    Certificates=[LbCertificate(CertificateArn=Ref(certs[index]))],
                    ListenerArn=Ref(ALBListenerHttps),
                )
            )

        t.add_resource(
            RecordSetGroup(
                f"R53AlbRecordGroup{index}",
                HostedZoneName=f"{domain_name}.",
                RecordSets=[
                    RecordSet(
                        Name=domain_name,
                        Type="A",
                        AliasTarget=AliasTarget(
                            HostedZoneId=GetAtt("ALBGophish", "CanonicalHostedZoneID"),
                            DNSName=GetAtt("ALBGophish", "DNSName"),
                        ),
                    ),
                    RecordSet(
                        Name=f"www.{domain_name}",
                        Type="A",
                        AliasTarget=AliasTarget(
                            HostedZoneId=GetAtt("ALBGophish", "CanonicalHostedZoneID"),
                            DNSName=GetAtt("ALBGophish", "DNSName"),
                        ),
                    ),
                ],
            )
        )

    return t.to_json()
