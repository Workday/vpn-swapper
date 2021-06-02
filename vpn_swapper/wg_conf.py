import logging
import subprocess
from configparser import ConfigParser

from .error import VpnSwapperException


class WgConf:
    def __init__(self, cp=None):
        self.cp = cp if cp is not None else self._create_blank_conf()

    def set_server(self, host, port, pubkey):
        self.cp['Peer'] = {'AllowedIPs': '0.0.0.0/0',
                           'PublicKey': pubkey,
                           'Endpoint': f'{host}:{port}'}

        logging.info(f'Set server to {host}:{port}')

    def get_pubkey(self):
        p = subprocess.run(['wg', 'pubkey'],
                           input=self.cp['Interface']['PrivateKey'].encode(),
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        if len(p.stderr) != 0:
            logging.error(f'Failed to generate private key: {p.stderr.decode()}')
            return None
        return p.stdout.decode().strip()

    def has_peers(self):
        return 'Peer' in self.cp

    def get_endpoint(self):
        if not self.has_peers():
            raise VpnSwapperException("Cannot get endpoint of configuration with no peers")
        ept = self.cp['Peer']['Endpoint'].split(':')
        return ept[0], int(ept[1])

    @classmethod
    def load(cls, f):
        cp = ConfigParser()
        cp.read_file(f)
        return cls(cp)

    @classmethod
    def loads(cls, s):
        cp = ConfigParser()
        cp.read_string(s)
        return cls(cp)

    def dump(self, f):
        self.cp.write(f)

    def _create_blank_conf(self):
        cp = ConfigParser()

        p = subprocess.run(['wg', 'genkey'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if len(p.stderr) != 0:
            logging.error(f'Failed to generate private key: {p.stderr.decode()}')
            return cp

        cp['Interface'] = {'PrivateKey': p.stdout.decode(),
                           'Address': '10.73.31.2/24',
                           'DNS': '8.8.8.8'}

        return cp
