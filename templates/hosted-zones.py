from troposphere import Export, Output, Ref, Template
from troposphere.route53 import HostedZone


def sceptre_handler(sceptre_user_data):
    t = Template()

    t.set_version("2010-09-09")

    t.set_description("""Gophish Phishing Platform Hosted Zones""")

    for index in range(len(sceptre_user_data["domains"])):
        domain_name = sceptre_user_data["domains"][index]

        t.add_resource(HostedZone(f"Domain{index}", Name=domain_name))

        t.add_output(
            Output(
                f"GophishHostedZoneId{index}",
                Description=f"Hosted zone ID for {domain_name}",
                Value=Ref(f"Domain{index}"),
                Export=Export(f"GophishHostedZoneId{index}"),
            )
        )

    return t.to_json()
