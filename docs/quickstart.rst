Quickstart on Debian systems
~~~~~~~~~~~~~~~~~~~~~~


Assuming there is no previous configuration in /etc/onionbalance :

.. code-block:: bash

   $ sudo apt-get install onionbalance
   $ /usr/sbin/onionbalance-config
   $ sudo cp ./config/master/*.key /etc/onionbalance/
   $ sudo cp ./config/master/config.yaml /etc/onionbalance/
   $ sudo chown onionbalance:onionbalance /etc/onionbalance/*.key
   $ sudo service onionbalance restart
   $ sudo tail -f /var/log/onionbalance/log

Check the logs. The following warnings are expected:
"Error generating descriptor: No introduction points for service ..."

Copy the "instance_torrc" and "private_key" files from each of the directories named ./config/srv1 , srv2, ... to each Tor servers providing the Onion Services.

Configure and start the services - the Onion Service on onionbalance should be ready within 10 minutes.


