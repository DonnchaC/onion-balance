# -*- coding: utf-8 -*-
import os

"""
Define default config options for the management server
"""

# Set default configuration options for the management server

REPLICAS = 2
HSDIR_SET = 3  # Publish each descriptor to 3 consecutive HSDirs
MAX_INTRO_POINTS = 10
DESCRIPTOR_VALIDITY_PERIOD = 24 * 60 * 60
DESCRIPTOR_OVERLAP_PERIOD = 60 * 60
DESCRIPTOR_UPLOAD_PERIOD = 60 * 60  # Re-upload descriptor every hour
REFRESH_INTERVAL = 10 * 60
PUBLISH_CHECK_INTERVAL = 5 * 60
HEALTH_CHECK_INTERVAL = 60
INITIAL_DELAY = 45  # Wait for instance descriptors before publishing

LOG_LOCATION = os.environ.get('ONIONBALANCE_LOG_LOCATION')
LOG_LEVEL = os.environ.get('ONIONBALANCE_LOG_LEVEL', 'info')

STATUS_SOCKET_LOCATION = os.environ.get('ONIONBALANCE_STATUS_SOCKET_LOCATION',
                                        '/var/run/onionbalance/control')

TOR_ADDRESS = '127.0.0.1'
TOR_PORT = 9051
TOR_CONTROL_PASSWORD = None
TOR_CONTROL_SOCKET = os.environ.get('ONIONBALANCE_TOR_CONTROL_SOCKET',
                                    '/var/run/tor/control')

# Upload multiple distinct descriptors containing different subsets of
# the available introduction points
DISTINCT_DESCRIPTORS = True

# Store global data about onion services and their instance nodes.
services = []

controller = None
