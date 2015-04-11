# OnionBalance

WARNING: THIS IS VERY EXPERIMENTAL, ROUGH CODE. THIS IS NOT READY TO BE USED
FOR PRODUCTION. IT MAY CONTAIN CRITICAL SECURITY OR PERFORMANCE BUGS.

## Overview

The onion service load balancer allows an operator to distribute requests
for their onion service to between 1 and 10 separate Tor instances. Each
Tor instance can run completely independently with no knowledge of any other
instances.

The load balancer is the only system which needs to store the onion services's private key. As the load balancer handles no hidden service traffic it's
risk of deanonymisation by traffic analysis attacks is reduced.

## Installation

### Load Balancing Instances

Each load-balancing instance is an onion service configured with a unique
private key. To minimize the disclosure of information about your onion
service configuration it is advisable to configure some form of onion service
authentication.

The individual load balancing instances can use a standard Tor client.

#### Management Server

##### Generate a onion service key

You can use your existing onion service `private_key` or generate a new
one using OpenSSL.

    $ openssl genrsa -out private_key 1024

##### Encrypt an onion service private key

Your master onion service private key can be protected by encrypting it
while it is stored on disk. Due to limitation in the underlying pycrypto
library, only DES-CBC, DES-EDE3-CBC, AES-128-CBC encrypted keys are supported.

    $ openssl rsa -des3 -in private_key -out private_key.enc

##### Configure Tor on the management server

For this tool to work you need a version of Tor with the ability to fetch
and upload HS descriptors. Until these features are merged into Tor, you can
use my patched Tor branch.

    $ git clone https://github.com/DonnchaC/tor.git
    $ cd tor
    $ git checkout hs-fetch-and-post-cmds

The `docs/torrc` contains a sample Tor config file which is suitable for the
management server.

##### Install the management server

The code for the onion load balancer can be using git.

    $ git clone https://github.com/DonnchaC/onion-balance.git
    $ cd onion-balance

The management server requires a number of Python dependencies. These can
be install using pip.

    $ pip install -r requirements.txt

For onion service descriptor parsing you need a version of stem >= `1.3.0-dev`.

    $ git clone https://git.torproject.org/stem.git
    $ sudo python stem/setup.py install

## Configuration

Each load balancing Tor instance is listed by it's unique onion address.
An optional authentication cookie can also be provided if the back-end onion
service is using some form of descriptor encryption.

An example config file is provided in `config.yaml.example`.

## Running

Once your load balancing instances are running, you can run the onion load balancer by starting the management server:

    $ python onion-balance/manager.py -c config.yaml

