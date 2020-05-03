#
# OnionBalance deployer
# The script is meant to be idempotent. Once an initial OnionBalance conf is
# generated the script can be run multiple times if needed.
#
# Usage: replace the variables below
# Ensure that host running fabric can ssh into the servers
#
# $ sudo apt-get install fabric
# $ fab deploy
#
# When needed:
# $ fab show_onionbalance_status
#

from fabric.api import env,hosts,run,execute,roles,sudo,get,put,parallel,cd
import os.path
from os.path import join as pj
import fabric.contrib.files
import sys
from time import sleep

#
# Configure the following variables
#

env.roledefs['ob-servers'] = ["REPLACE ME with the onionblanance server name"]
env.roledefs['torservers'] = ["REPLACE ME with a tor server name", "..."]

onion_service_external_port = 80
onion_service_target = '127.0.0.1:80'

# local path with no ~ or ./
local_master_conf_path = "onionbalance_master_conf"

onion_service_dir_prefix = "onionbalanced_"

#
# End
#

@parallel
@roles('torservers', 'ob-servers')
def apt_update():
    """Update APT cache"""
    sudo('apt-get -q update')

@roles('ob-servers')
def install_onionbalance():
    print("Installing OnionBalance")
    sudo('apt-get -q -y install onionbalance')
    # Create UNIX socket dir if needed
    sudo("mkdir -p /var/run/onionbalance")
    sudo("chown onionbalance:onionbalance /var/run/onionbalance")

@roles('torservers')
def install_tor():
    print("Installing Tor")
    sudo('apt-get -q -y install tor')

master_ob_server = env.roledefs['ob-servers'][0]
@hosts(master_ob_server)
def generate_master_conf():
    # This is run on one OnionBalance only - it does not matter which one
    if os.path.exists(local_master_conf_path):
        print("*" * 50)
        print("%s is already existing - not overwriting it!" % \
              local_master_conf_path)
        print("*" * 50)
        return

    print("Generating OnionBalance once on the master server")
    num_torservers = len(env.roledefs['torservers'])
    cmd = "/usr/sbin/onionbalance-config -n %d --service-virtual-port %d " \
        "--service-target %s --output ~/onionbalance_master_conf.tmp" % (
        num_torservers,
        onion_service_external_port,
        onion_service_target,
    )
    run(cmd)
    print("Master OnionBalance configuration generated - fetching it")
    get("~/onionbalance_master_conf.tmp/*", local_master_conf_path)
    sudo("rm ~/onionbalance_master_conf.tmp -rf")

def check_onion_service_target():
    try:
        assert ':' in onion_service_target, "missing colon"
        ipaddr, port = onion_service_target.split(':')
        int(port)
        parts = ipaddr.split('.')
        assert len(parts) == 4, "incorrect number of IPv4 octects"
        for x in parts:
            assert 255 >= int(x) >= 0, "incorrect octect"
    except Exception as e:
        print(e)
        print("onion_service_target should be <ipaddr>:<port>")
        sys.exit(1)


@roles('ob-servers')
def install_onionbalance_configs():
    print("Installing OnionBalance config")
    put(
        pj("./", local_master_conf_path, "master", "*.key"),
        "/etc/onionbalance/",
        use_sudo=True
    )
    put(
        pj("./", local_master_conf_path, "master", "config.yaml"),
        "/etc/onionbalance/",
        use_sudo=True
    )
    sudo("chown onionbalance:onionbalance /etc/onionbalance/*.key")

@roles('ob-servers')
def restart_onionbalance():
    sudo("service onionbalance restart")
    sleep(5)
    sudo("service onionbalance status | cat")

def parse_service_name(confdir):
    """Extract HiddenServiceDir value from instance_torrc
    """
    conf_fn = "%s/%s/instance_torrc" % (local_master_conf_path, confdir)
    with open(conf_fn) as f:
        for line in f:
            if line.startswith("HiddenServiceDir"):
                return line.split()[1]

    raise Exception("HiddenServiceDir parameter not found in %s" % conf_fn)

@roles('torservers')
def install_tor_configs():
    current_host_num = env.roledefs['torservers'].index(env.host_string) + 1
    confdir = "srv%d" % current_host_num
    print("Installing Tor config from directory %s" % confdir)
    # service_name is a random string, service_dir is more meaningful
    service_name = parse_service_name(confdir)
    service_dir = "%s%s" % (onion_service_dir_prefix, service_name)
    print("Service name: %s" % service_dir)

    if fabric.contrib.files.contains("/etc/tor/torrc", service_dir,
                                     use_sudo=True):
        print("Config chunk already present, skipping...")
        return

    config_chunk = """# Created by OnionBalance fabric helper
HiddenServiceDir /var/lib/tor/%s
HiddenServicePort %d %s
""" % (service_dir, onion_service_external_port, onion_service_target)

    print("Injecting:\n--%s--" % config_chunk)
    fabric.contrib.files.append("/etc/tor/torrc", config_chunk,
                                    use_sudo=True)

    sudo("mkdir -p /var/lib/tor/%s" % service_dir)
    put(
        pj("./", local_master_conf_path, confdir, service_name, "private_key"),
        pj("/var/lib/tor", service_dir, "private_key"),
        use_sudo=True
    )

    sudo("chown debian-tor:debian-tor %s" % \
         pj("/var/lib/tor", service_dir))
    sudo("chown debian-tor:debian-tor %s" % \
         pj("/var/lib/tor", service_dir, "private_key"))
    sudo("chmod 700 %s" % pj("/var/lib/tor", service_dir))

@roles('torservers')
def start_and_reload_tor():
    sudo("service tor start")
    sudo("service tor reload")

@roles('torservers')
def show_tor_service_status():
    sudo("service tor status | cat")

@roles('ob-servers')
def show_onionbalance_status():
    print("Fetching OnionBalance status")
    sudo("socat - unix-connect:/var/run/onionbalance/control")

def deploy():
    """Update APT, deploy daemons, configure OnionBalance
    """
    check_onion_service_target()
    execute(apt_update)
    execute(install_onionbalance)
    execute(install_tor)
    execute(generate_master_conf)

    execute(install_tor_configs)
    execute(start_and_reload_tor)
    execute(show_tor_service_status)

    execute(install_onionbalance_configs)
    execute(restart_onionbalance)
    execute(show_onionbalance_status)

