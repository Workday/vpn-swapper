import logging
from socket import timeout

from paramiko import SSHClient, AutoAddPolicy

from .wg_conf import WgConf
from .error import VpnSwapperException


class VPNHost:
    def __init__(self, host, ssh_key):
        self.host = host
        self.ssh = SSHClient()

        self.ssh.set_missing_host_key_policy(AutoAddPolicy)  # no one checks these anyways
        try:
            self.ssh.connect(self.host, username='ubuntu', pkey=ssh_key, timeout=5)
        except timeout:
            retry = input("SSH connections are taking a while, do you have permissions to access: [y/N]") == 'y'
            if retry:
                self.ssh.connect(self.host, username='ubuntu', pkey=ssh_key)
            else:
                raise VpnSwapperException("SSH timed out, assure that you can connect to the VPN hosts")

    def take(self, pubkey):
        self.ssh.exec_command(f'sudo wg set wg0 peer {pubkey} allowed-ips 10.73.31.2')

    def get_server_conf(self):
        _, stdout, stderr = self.ssh.exec_command('sudo wg showconf wg0')

        err = stderr.read().decode()
        if err:
            logging.error(err)
            return None

        return WgConf.load(stdout)

    def get_ec2_instance_id(self):
        _, stdout, stderr = self.ssh.exec_command('curl -s http://169.254.169.254/latest/meta-data/instance-id')

        err = stderr.read().decode()
        if err:
            logging.error(err)
            return None

        return stdout.read().decode()

    def __del__(self):
        self.ssh.close()
