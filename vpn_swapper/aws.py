import logging
from itertools import chain as flatten

import boto3
from botocore.exceptions import ClientError

from .error import VpnSwapperException


class AwsClient:

    def __init__(self, profile, region):
        s = boto3.Session(profile_name=profile, region_name=region)
        self.ec2 = s.client('ec2')
        self.ssm = s.client('ssm')

    def get_vpn_hosts(self):
        response = self.ec2.describe_instances(Filters=[
            {'Name': 'tag:Name', 'Values': ['vpn-asg']},
            {'Name': 'instance-state-name', 'Values': ['running']}])

        instances = flatten.from_iterable([instance for instance in [reservation['Instances']
                                                                     for reservation
                                                                     in response['Reservations']]])
        return [i['PublicIpAddress'] for i in instances]

    def terminate_host(self, instance_id):
        self.ec2.terminate_instances(InstanceIds=[instance_id])

    def modify_security_group_rule(self, ip, revoke):
        group_name = 'vpn-swapper-sg'
        cidr = f"{ip}/32"

        response = self.ec2.describe_security_groups(
            Filters=[
                dict(Name='group-name', Values=[group_name])
            ]
        )

        group_id = response['SecurityGroups'][0]['GroupId']
        rule_base = {'IpProtocol': 'tcp',
                     'FromPort': 22,
                     'ToPort': 22,
                     'IpRanges': [{'CidrIp': cidr}]}

        if revoke:
            data = self.ec2.revoke_security_group_ingress(GroupId=group_id, IpPermissions=[rule_base])
            logging.debug(f'Ingress Successfully Set {data}')
        else:
            data = self.ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[rule_base])
            logging.debug(f'Ingress Successfully Revoked {data}')

    def get_vpn_privkey(self, path):
        try:
            return self.ssm.get_parameter(Name=path, WithDecryption=True)['Parameter']['Value']
        except ClientError as ex:
            msg = "A private ssh key was not found in AWS SSM. If an ssh key exists, then the config\n parameter " \
                "'ssh_key_path' may need to be updated to point to it. "
            raise VpnSwapperException(msg)
