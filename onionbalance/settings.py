# -*- coding: utf-8 -*-

"""
Implements the generation and loading of configuration files.
"""
from builtins import input, range
import os
import sys
import errno
import argparse
import getpass
import logging
import pkg_resources

import yaml
import Crypto.PublicKey

from onionbalance import config
from onionbalance import util
from onionbalance import log

import onionbalance.service
import onionbalance.instance

logger = log.get_logger()


def parse_config_file(config_file):
    """
    Parse config file containing service information
    """
    config_path = os.path.abspath(config_file)
    if os.path.exists(config_path):
        with open(config_file, 'r') as handle:
            config_data = yaml.load(handle.read())
            logger.info("Loaded the config file '%s'.", config_path)
    else:
        logger.error("The specified config file '%s' does not exist. The "
                     "onionbalance-config tool can generate the required "
                     "keys and config files.", config_path)
        sys.exit(1)

    # Rewrite relative paths in the config to be relative to the config
    # file directory
    config_directory = os.path.dirname(config_path)
    for service in config_data.get('services'):
        if not os.path.isabs(service.get('key')):
            service['key'] = os.path.join(config_directory, service['key'])

        service.setdefault('health_check', {})
        # Do not run health checks by default
        service['health_check'].setdefault('type', None)
        service['health_check'].setdefault('port', 80)
        service['health_check'].setdefault('path', '/')
        service['health_check'].setdefault('timeout', 15)

    return config_data


def initialize_services(controller, services_config):
    """
    Load keys for services listed in the config
    """

    # Load the keys and config for each onion service
    for service in services_config:
        try:
            service_key = util.key_decrypt_prompt(service.get("key"))
        except (IOError, OSError) as e:
            if e.errno == errno.ENOENT:
                logger.error("Private key file %s could not be found. "
                             "Relative paths in the config file are loaded "
                             "relative to the config file directory.",
                             service.get("key"))
                sys.exit(1)
            elif e.errno == errno.EACCES:
                logger.error("Permission denied to private key %s.",
                             service.get("key"))
                sys.exit(1)
            else:
                raise
        # Key file was read but a valid private key was not found.
        if not service_key:
            logger.error("Private key %s could not be loaded. It is a not "
                         "valid 1024 bit PEM encoded RSA private key",
                         service.get("key"))
            sys.exit(1)
        else:
            # Successfully imported the private key
            onion_address = util.calc_onion_address(service_key)
            logger.debug("Loaded private key for service %s.onion.",
                         onion_address)

        # Load all instances for the current onion service
        instance_config = service.get("instances", [])
        if not instance_config:
            logger.error("Could not load any instances for service "
                         "%s.onion.", onion_address)
            sys.exit(1)
        else:
            instances = []
            for instance in instance_config:
                instances.append(onionbalance.instance.Instance(
                    controller=controller,
                    onion_address=instance.get("address"),
                    authentication_cookie=instance.get("auth")
                ))

            logger.info("Loaded %d instances for service %s.onion.",
                        len(instances), onion_address)

        # Store service configuration in config.services global
        config.services.append(onionbalance.service.Service(
            controller=controller,
            service_key=service_key,
            instances=instances,
            health_check_conf=service['health_check']
        ))

        # Store a global reference to current controller connection
        config.controller = controller


def parse_cmd_args():
    """
    Parses and returns command line arguments for config generator
    """

    parser = argparse.ArgumentParser(
        description="onionbalance-config generates config files and keys for "
        "OnionBalance instances and management servers. Calling without any "
        "options will initiate an interactive mode.")

    parser.add_argument("--key", type=str, default=None,
                        help="RSA private key for the master onion service.")

    parser.add_argument("-p", "--password", type=str, default=None,
                        help="Optional password which can be used to encrypt"
                        "the master service private key.")

    parser.add_argument("-n", type=int, default=2, dest="num_instances",
                        help="Number of instances to generate (default: "
                        "%(default)s).")

    parser.add_argument("-t", "--tag", type=str, default='srv',
                        help="Prefix name for the service instances "
                        "(default: %(default)s).")

    parser.add_argument("--output", type=str, default='config/',
                        help="Directory to store generate config files. "
                        "The directory will be created if it does not "
                        "already exist.")

    parser.add_argument("--no-interactive", action='store_true',
                        help="Try to run automatically without prompting for"
                        "user input.")

    parser.add_argument("-v", type=str, default="info", dest='verbosity',
                        help="Minimum verbosity level for logging. Available "
                        "in ascending order: debug, info, warning, error, "
                        "critical).  The default is info.")

    parser.add_argument("--service-virtual-port", type=str,
                        default="80",
                        help="Onion service port for external client "
                        "connections (default: %(default)s).")

    # TODO: Add validator to check if the target host:port line makes sense.
    parser.add_argument("--service-target", type=str,
                        default="127.0.0.1:80",
                        help="Target IP and port where your service is "
                        "listening (default: %(default)s).")

    # .. todo:: Add option to specify HS host and port for instance torrc

    parser.add_argument('--version', action='version',
                        version='onionbalance %s' % onionbalance.__version__)

    return parser


def generate_config():
    """
    Entry point for interactive config file generation.
    """

    # Parse initial command line options
    args = parse_cmd_args().parse_args()

    # Simplify the logging output for the command line tool
    logger = log.get_config_generator_logger()

    logger.info("Beginning OnionBalance config generation.")

    # If CLI options have been provided, don't enter interactive mode
    # Crude check to see if any options beside --verbosity are set.
    verbose = True if '-v' in sys.argv else False

    if ((len(sys.argv) > 1 and not verbose) or len(sys.argv) > 3 or
            args.no_interactive):
        interactive = False
        logger.info("Entering non-interactive mode.")
    else:
        interactive = True
        logger.info("No command line arguments found, entering interactive "
                    "mode.")

    logger.setLevel(logging.__dict__[args.verbosity.upper()])

    # Check if output directory exists, if not try create it
    output_path = None
    if interactive:
        output_path = input("Enter path to store generated config "
                            "[{}]: ".format(os.path.abspath(args.output)))
    output_path = output_path or args.output
    try:
        util.try_make_dir(output_path)
    except OSError:
        logger.exception("Problem encountered when trying to create the "
                         "output directory %s.", os.path.abspath(output_path))
    else:
        logger.debug("Created the output directory '%s'.",
                     os.path.abspath(output_path))

    # The output directory should be empty to avoid having conflict keys
    # or config files.
    if not util.is_directory_empty(output_path):
        logger.error("The specified output directory is not empty. Please "
                     "delete any files and folders or specify another output "
                     "directory.")
        sys.exit(1)

    # Load master key if specified
    key_path = None
    if interactive:
        # Read key path from user
        key_path = input("Enter path to master service private key "
                         "(Leave empty to generate a key): ")
    key_path = args.key or key_path
    if key_path:
        if not os.path.isfile(key_path):
            logger.error("The specified master service private key '%s' "
                         "could not be found. Please confirm the path and "
                         "file permissions are correct.", key_path)
            sys.exit(1)
        else:
            # Try load the specified private key file
            master_key = util.key_decrypt_prompt(key_path)
            if not master_key:
                logger.error("The specified master private key %s could not "
                             "be loaded.", os.path.abspath(master_key))
                sys.exit(1)
            else:
                master_onion_address = util.calc_onion_address(master_key)
                logger.info("Successfully loaded a master key for service "
                            "%s.onion.", master_onion_address)

    else:
        # No key specified, begin generating a new one.
        master_key = Crypto.PublicKey.RSA.generate(1024)
        master_onion_address = util.calc_onion_address(master_key)
        logger.debug("Created a new master key for service %s.onion.",
                     master_onion_address)

    # Finished loading/generating master key, now try generate keys for
    # each service instance
    num_instances = None
    if interactive:
        num_instances = input("Number of instance services to create "
                              "[{}]: ".format(args.num_instances))
        # Cast to int if a number was specified
        try:
            num_instances = int(num_instances)
        except ValueError:
            num_instances = None
    num_instances = num_instances or args.num_instances
    logger.debug("Creating %d service instances.", num_instances)

    tag = None
    if interactive:
        tag = input("Provide a tag name to group these instances "
                    "[{}]: ".format(args.tag))
    tag = tag or args.tag

    # Create HiddenServicePort line for instance torrc file
    service_virtual_port = None
    if interactive:
        service_virtual_port = input("Specify the service virtual port (for "
                                     "client connections) [{}]: ".format(
                                         args.service_virtual_port))
    service_virtual_port = service_virtual_port or args.service_virtual_port

    service_target = None
    if interactive:
        # In interactive mode, change default target to match the specified
        # virtual port
        default_service_target = u'127.0.0.1:{}'.format(service_virtual_port)
        service_target = input("Specify the service target IP and port (where "
                               "your service is listening) [{}]: ".format(
                                   default_service_target))
        service_target = service_target or default_service_target
    service_target = service_target or args.service_target
    torrc_port_line = u'HiddenServicePort {} {}'.format(service_virtual_port,
                                                        service_target)

    instances = []
    for i in range(0, num_instances):
        instance_key = Crypto.PublicKey.RSA.generate(1024)
        instance_address = util.calc_onion_address(instance_key)
        logger.debug("Created a key for instance %s.onion.",
                     instance_address)
        instances.append((instance_address, instance_key))

    # Write master service key to directory
    master_passphrase = None
    if interactive:
        master_passphrase = getpass.getpass(
            "Provide an optional password to encrypt the master private "
            "key (Not encrypted if no password is specified): ")
    master_passphrase = master_passphrase or args.password

    # Finished reading input, starting to write config files.
    master_dir = os.path.join(output_path, 'master')
    util.try_make_dir(master_dir)
    master_key_file = os.path.join(master_dir,
                                   '{}.key'.format(master_onion_address))
    with open(master_key_file, "wb") as key_file:
        os.chmod(master_key_file, 384)  # chmod 0600 in decimal
        key_file.write(master_key.exportKey(passphrase=master_passphrase))
        logger.debug("Successfully wrote master key to file %s.",
                     os.path.abspath(master_key_file))

    # Create YAML OnionBalance settings file for these instances
    service_data = {'key': '{}.key'.format(master_onion_address)}
    service_data['instances'] = [{'address': address,
                                  'name': '{}{}'.format(tag, i+1)} for
                                 i, (address, _) in enumerate(instances)]
    settings_data = {'services': [service_data]}
    config_yaml = yaml.safe_dump(settings_data, default_flow_style=False)

    config_file_path = os.path.join(master_dir, 'config.yaml')
    with open(config_file_path, "w") as config_file:
        config_file.write(u"# OnionBalance Config File\n")
        config_file.write(config_yaml)
        logger.info("Wrote master service config file '%s'.",
                    os.path.abspath(config_file_path))

    # Write master service torrc
    master_torrc_path = os.path.join(master_dir, 'torrc-server')
    master_torrc_template = pkg_resources.resource_string(__name__,
                                                          'data/torrc-server')
    with open(master_torrc_path, "w") as master_torrc_file:
        master_torrc_file.write(master_torrc_template.decode('utf-8'))

    # Try generate config files for each service instance
    for i, (instance_address, instance_key) in enumerate(instances):
        # Create a numbered directory for instance
        instance_dir = os.path.join(output_path, '{}{}'.format(tag, i+1))
        instance_key_dir = os.path.join(instance_dir, instance_address)
        util.try_make_dir(instance_key_dir)
        os.chmod(instance_key_dir, 1472)  # chmod 2700 in decimal

        instance_key_file = os.path.join(instance_key_dir, 'private_key')
        with open(instance_key_file, "wb") as key_file:
            os.chmod(instance_key_file, 384)  # chmod 0600 in decimal
            key_file.write(instance_key.exportKey())
            logger.debug("Successfully wrote key for instance %s.onion to "
                         "file.", instance_address)

        # Write torrc file for each instance
        instance_torrc = os.path.join(instance_dir, 'instance_torrc')
        instance_torrc_template = pkg_resources.resource_string(
            __name__, 'data/torrc-instance')
        with open(instance_torrc, "w") as torrc_file:
            torrc_file.write(instance_torrc_template.decode('utf-8'))
            # The ./ relative path prevents Tor from raising relative
            # path warnings. The relative path may need to be edited manual
            # to work on Windows systems.
            torrc_file.write(u"HiddenServiceDir {}\n".format(
                instance_address))
            torrc_file.write(u"{}\n".format(torrc_port_line))

    # Output final status message
    logger.info("Done! Successfully generated an OnionBalance config and %d "
                "instance keys for service %s.onion.",
                num_instances, master_onion_address)

    sys.exit(0)
