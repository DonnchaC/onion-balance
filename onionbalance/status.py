# -*- coding: utf-8 -*-
# OnionBalance - Status
# Copyright: 2015 Federico Ceratto
# Released under GPLv3, see COPYING file

"""
Provide status over Unix socket
Default path: /var/run/onionbalance/control
"""

from datetime import datetime
import os
import errno
import threading
import socket
from socketserver import BaseRequestHandler, ThreadingMixIn, UnixStreamServer

from onionbalance import log
from onionbalance import config

logger = log.get_logger()


class StatusSocketHandler(BaseRequestHandler):
    """
    Handler for new domain socket connections
    """
    def send_status(self):
        """
        Prepare and output the status summary when a connection is received
        """
        time_format = "%Y-%m-%d %H:%M:%S"
        response = []
        for service in config.services:
            if service.uploaded:
                service_timestamp = service.uploaded.strftime(time_format)
            else:
                service_timestamp = "[not uploaded]"
            response.append("{}.onion {}".format(service.onion_address,
                                                 service_timestamp))

            healthcheck = service.health_check_conf['type'] != None
            for instance in service.instances:
                if not instance.timestamp:
                    response.append("  {}.onion [offline]".format(
                        instance.onion_address))
                else:
                    response.append("  {}.onion {} {} IPs".format(
                        instance.onion_address,
                        instance.timestamp.strftime(time_format),
                        len(instance.introduction_points)))

                if healthcheck:
                    if instance.is_healthy:
                        ts = datetime.fromtimestamp(instance.last_check_time)
                        ts = ts.strftime('%H:%M:%S')
                        response[-1] += " [up at %s]" % ts
                    elif instance.is_healthy == False:
                        ts = datetime.fromtimestamp(instance.last_check_time)
                        ts = ts.strftime('%H:%M:%S')
                        response[-1] += " [down at %s]" % ts
                    # if is_healthy == None, show nothing

        response.append("")
        self.request.sendall('\n'.join(response).encode('utf-8'))

    def handle(self):
        try:
            self.send_status()
        except Exception as e:
            logger.warning("Error returning status: %s" % e, exc_info=True)


class ThreadingSocketServer(ThreadingMixIn, UnixStreamServer):
    """
    Unix socket server with threading
    """
    pass


class StatusSocket(object):
    """
    Create a Unix domain socket which emits a summary of the OnionBalance
    status when a client connects.
    """

    def __init__(self, config):
        """
        Create the Unix domain socket status server and start in a thread

        Example::
            socat - unix-connect:/var/run/onionbalance/control

            uweyln7jhkyaokka.onion 2016-05-01 11:08:56
              r523s7jx65ckitf4.onion [offline]
              v2q7ujuleky7odph.onion 2016-05-01 11:00:00 3 IPs
        """
        self.unix_socket_filename = config.STATUS_SOCKET_LOCATION
        self.cleanup_socket_file()

        logger.debug("Creating status socket at %s", self.unix_socket_filename)
        try:
            self.server = ThreadingSocketServer(self.unix_socket_filename,
                                                StatusSocketHandler)

            # Start running the socket server in a another thread
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True  # Exit daemon when main thread stops
            server_thread.start()

        except (OSError, socket.error):
            logger.error("Could not start status socket at %s. Does the path "
                         "exist? Do you have permission?",
                         status_socket_location)

    def cleanup_socket_file(self):
        """
        Try to remove the socket file if it exists already
        """
        try:
            os.unlink(self.unix_socket_filename)
        except OSError as e:
            # Reraise if its not a FileNotFound exception
            if e.errno != errno.ENOENT:
                raise

    def close(self):
        """
        Close the unix domain socket and remove its file
        """
        try:
            self.server.shutdown()
            self.server.server_close()
            self.cleanup_socket_file()
        except AttributeError:
            pass
        except OSError:
            logger.exception("Error when removing the status socket")
