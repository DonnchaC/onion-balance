# -*- coding: utf-8 -*-
# OnionBalance - Service health checking
# Copyright: 2015 Federico Ceratto
# Released under GPLv3, see COPYING file
#
# Requires python3-socks - https://github.com/Anorov/PySocks

"""
Check service health using TCP, HTTP, HTTPS
"""

import urllib.request
import socket
from time import time

from onionbalance import log
import onionbalance

try:
    import socks
    from sockshandler import SocksiPyHandler
    socks_available = True
except ImportError:
    socks_available = False

logger = log.get_logger()

USER_AGENT_HEADER = 'OnionBalance/%s' % onionbalance.__version__


def check_tcp(onion_addr, port_number, timeout):
    """Check for Onion Service connectivity with a TCP connect
    """
    if not socks_available:
        logger.error("please install the pysocks library")
        return

    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
    s.settimeout(timeout)
    logger.debug("Checking TCP %s:%d", onion_addr, port_number)
    try:
        t = time()
        s.connect(("%s.onion" % onion_addr, port_number))
        delta = time() - t
        is_healthy = True
    except:
        delta = time() - t
        is_healthy = False
    finally:
        s.close()

    return is_healthy, t, delta


def _check_url(url, timeout):
    """Check for HTTP[S] connectivity over Tor"""

    opener = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 9050))
    opener.addheaders = [('User-agent', USER_AGENT_HEADER)]
    logger.debug("Checking %s", url)
    try:
        t = time()
        opener.open(url, None, timeout).read(1024)
        is_healthy = True
    except Exception as e:
        logger.debug("Check exception %s", e)
        is_healthy = False

    return is_healthy, t, time() - t


def check_http(onion_addr, port_number, path, timeout):
    """Check for Onion Service connectivity over HTTP using GET
    """
    path = path.lstrip('/')
    url = "http://%s.onion:%d/%s" % (onion_addr, port_number, path)
    return _check_url(url, timeout)


def check_https(onion_addr, port_number, path, timeout):
    """Check for Onion Service connectivity over HTTPS using GET
    """
    path = path.lstrip('/')
    url = "https://%s.onion:%d/%s" % (onion_addr, port_number, path)
    return _check_url(url, timeout)
