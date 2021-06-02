from unittest.mock import patch, MagicMock

from vpn_swapper.aws import AwsClient

from .test_data import *

class TestAws:

    @patch('boto3.client', autospec=True)
    def test_get_vpn_hosts(self, client_mock):
        client_mock.return_value.describe_instances.return_value = instances()
        ec2 = AwsClient('some-region')
        hosts = ec2.get_vpn_hosts()
        assert '13.56.160.4' in hosts
        assert '54.67.116.79' in hosts
