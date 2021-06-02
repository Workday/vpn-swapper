import argparse
import ctypes
import io
import logging
import os
import platform
import subprocess
import sys
from traceback import format_exc

from botocore.exceptions import ClientError
from paramiko.rsakey import RSAKey

from .aws import AwsClient
from .config import Config
from .error import VpnSwapperException
from .log import setup_logging
from .vpn_host import VPNHost
from .wg_conf import WgConf


def get_client_config(config):
    try:
        with open(config['wg_conf_file'], 'r') as f:
            return WgConf.load(f)
    except FileNotFoundError:
        logging.info("No wireguard config found, generating new one")
        return WgConf()


def checked_sp(cmd):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(e)
        logging.debug(b'Stdout: ' + e.stdout)
        logging.debug(b'Stderr: ' + e.stderr)
        raise VpnSwapperException(f'Failed to run command {cmd}: {e}') from e

    logging.debug(b'Stdout: ' + p.stdout)
    logging.debug(b'Stderr: ' + p.stderr)


# XXX: This is hacky, it will be solved moving off wg-quick(8) and adding our own routes
def vpn_connect(config, wg):
    with open(config['wg_conf_file'], 'w') as f:
        wg.dump(f)

    if "Windows" in platform.system():
        checked_sp(['wireguard.exe', '/installtunnelservice', config['wg_conf_file']])
    else:
        checked_sp(['sudo', 'wg-quick', 'up', config['wg_conf_file']])


# XXX: The incongruity of this will be fixed when we move off of wg-quick(8). However, for the moment I'm lazy
def vpn_disconnect(config):
    if "Windows" in platform.system():
        tunnel_name = os.path.splitext(os.path.basename(config['wg_conf_file']))[0]

        try:
            checked_sp(['wireguard.exe', '/uninstalltunnelservice', tunnel_name])
        except subprocess.CalledProcessError:
            logging.error(f"Failed to find a previous tunnel service, it may not have terminated cleanly, attempting "
                          f"to continue")
    else:
        checked_sp(['sudo', 'wg-quick', 'down', config['wg_conf_file']])

    os.remove(config['wg_conf_file'])


# XXX: This function is a race condition, we need a better solution than this, and one day a real developer will look
# at this and cry
def acquire_vpn_host(hosts, ssh_key, client_pubkey, aws):
    for host in hosts:
        vpn_host = VPNHost(host, ssh_key)

        # ENTER RACE
        server_conf = vpn_host.get_server_conf()
        if server_conf.has_peers():
            logging.warning(f"Attempted to connect to in-use VPN: {host}")
            continue

        vpn_host.take(client_pubkey)
        # EXIT RACE

        logging.info(f"Successfully connected to VPN: {host}")

        try:
            aws.modify_security_group_rule(host, False)
        except ClientError as ex:
            logging.error(f"Ran into an issue adding to security group, may not cause issues: {ex}")

        return vpn_host

    msg = "Unable to find open VPN"
    logging.error(msg)
    raise VpnSwapperException(msg)


def add_flag(parser, *args, **kwargs):
    parser.add_argument(*args, action='store_true', default=False, **kwargs)


def add_arg(parser, *args, **kwargs):
    parser.add_argument(*args, **kwargs)


# https://stackoverflow.com/questions/1026431/cross-platform-way-to-check-admin-rights-in-a-python-script-under-windows
def get_admin_status():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return is_admin


def setup_config_and_logging(args):
    # We just dump everything to stdout for a reasonable default
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    add_flag(parser, "-d", "--debug", help="Add debugging messages to the log")
    add_flag(parser, "--log-libraries", help='This option prints debugging messages for dependencies')
    add_flag(parser, "--terminate", help='Disconnect computer from the VPN system')
    add_arg(parser, "-l", "--logfile", help='Location to log to. If blank, logs to stdout')
    parsed = parser.parse_args(args)

    config = Config.from_args('vpn-swapper', parsed)

    setup_logging(config['debug'], config['log_libraries'], config['logfile'])

    logging.info('VPN Swapper is configured')

    return config


def generate_pkey_from_string(privkey):
    return RSAKey.from_private_key(io.StringIO(privkey))


def main(argv):
    if "Windows" in platform.system():
        if not get_admin_status():
            msg = "This script needs to run from an elevated prompt on Windows. Terminating"
            raise VpnSwapperException(msg)

    config = setup_config_and_logging(argv[1:])

    logging.info(f"Connecting to {config['region']} for VPN")
    aws = AwsClient(config['profile'], config['region'])
    ssh_key = generate_pkey_from_string(aws.get_vpn_privkey(config['ssh_key_path']))

    wg = get_client_config(config)

    if wg.has_peers():
        host, _ = wg.get_endpoint()
        current_vpn = VPNHost(host, ssh_key)

        # this was previously a race condition, needs to be above disconnect
        ec2_id = current_vpn.get_ec2_instance_id()

        # remove self from the SG
        try:
            aws.modify_security_group_rule(host, True)
        except ClientError as ex:
            logging.error(f"Ran into an issue adding to security group, may not cause issues: {ex}")

        vpn_disconnect(config)
        logging.info(f"Disconnected from {host}")

        aws.terminate_host(ec2_id)
        logging.info(f"Terminated {ec2_id} @ {host}")

    if config['terminate']:
        return

    hosts = aws.get_vpn_hosts()
    logging.debug(hosts)

    try:
        vpn_host = acquire_vpn_host(hosts, ssh_key, wg.get_pubkey(), aws)
    except Exception:
        logging.error("No open VPNs could be found, please wait for more instances to spin up, then try again")
        return

    wg.set_server(vpn_host.host, config['wg_port'], vpn_host.get_server_conf().get_pubkey())

    vpn_connect(config, wg)

    logging.info(f"Connected to {vpn_host.host}")


if __name__ == '__main__':
    try:
        main(sys.argv)
    except VpnSwapperException as e:
        logging.error(f"Program terminated by unhandled error: {e}")
        logging.debug(format_exc())
