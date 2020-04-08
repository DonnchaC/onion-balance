#!/usr/bin/env python3
#
# OnionBalance web dashboard
#

from argparse import ArgumentParser
from collections import namedtuple
from datetime import datetime
import socket

import bottle
from bottle import route, run, view

ob_local_unix_socket = "/var/run/onionbalance/control"

ob_sock = None

Instance = namedtuple('Instance', ['addr', 'status', 'introduction_points'])

def parse_ob_status():
    """Fetch onionbalance status from UNIX socket and parse it
    """
    # Example chunk:
    #yzulvrodn6f5odli.onion 2017-02-17 14:21:26
    #  ewsvgwag2futnuwh.onion [offline]
    #  xnvdrsotxmzo5emu.onion [offline]
    #  etxda7c2ul6tudbo.onion [offline]
    #  5ukxtgexy5zeqmcj.onion [offline]

    services = []
    chunk = ""
    ob_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        ob_sock.connect(ob_local_unix_socket)
        ob_sock.settimeout(0.1)
        chunk = ob_sock.recv(4096)
    finally:
        try:
            ob_sock.close()
        except:
            pass

    chunk = str(chunk, 'ascii')

    current_service = None
    for line in chunk.split("\n"):

        if current_service == None:
            # possible service "header"
            try:
                service_addr, service_status = line.split(None, 1)
                current_service = Instance(service_addr, service_status, [])
            except:
                pass

        else:
            if line.startswith("  "):
                # introduction point line
                tokens = line.split()
                current_service.introduction_points.append(tokens)
            else:
                # end of service block
                services.append(current_service)
                current_service = None

    return services


def parse_args():
    desc="""OnionBalance web dashboard"""
    parser = ArgumentParser(description=desc)
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-p', '--port', type=int, default=8080,
                        help="TCP port (default: 8080)")
    parser.add_argument('-H', '--listen-address', default="0.0.0.0",
                        help="IP address to listen on (default: 0.0.0.0)")
    parser.add_argument('-t', '--templates',
                        help="Templates search path")
    args = parser.parse_args()
    return args


# Bottle routes

@route("/")
@view("dashboard")
def index():
    try:
        ob_status = parse_ob_status()
        msg = None
    except Exception as e:
        ob_status = []
        msg = "Exception parsing onionbalance status: %s" % e

    tstamp = datetime.utcnow().strftime('%H:%M:%S')
    return dict(ob_services=ob_status, tstamp=tstamp, msg=msg)


def main():
    args = parse_args()
    if args.templates:
        bottle.TEMPLATE_PATH.insert(0, args.templates)
    run(host=args.listen_address, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
