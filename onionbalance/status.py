# -*- coding: utf-8 -*-
"""
Provide status over Unix socket
Default path: /var/run/onionbalance/control
"""
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
    def handle(self):
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

            for instance in service.instances:
                if not instance.timestamp:
                    response.append("  {}.onion [offline]".format(
                        instance.onion_address))
                else:
                    response.append("  {}.onion {} {} IPs".format(
                        instance.onion_address,
                        instance.timestamp.strftime(time_format),
                        len(instance.introduction_points)))
        response.append("")
        self.request.sendall('\n'.join(response).encode('utf-8'))


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

    def __init__(self, status_socket_location):
        """
        Create the Unix domain socket status server and start in a thread

        Example::
            socat - unix-connect:/var/run/onionbalance/control

            uweyln7jhkyaokka.onion 2016-05-01 11:08:56
              r523s7jx65ckitf4.onion [offline]
              v2q7ujuleky7odph.onion 2016-05-01 11:00:00 3 IPs
        """
        self.unix_socket_filename = status_socket_location
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
