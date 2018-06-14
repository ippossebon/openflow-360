import datetime
from collections import deque

class HostProperties (object):

    def __init__(self):
        self.reachable_through_ports = deque()
        self.last_port = None
        self._knownIPsTimeout = {}
        self.last_mile = False

    def addUniqueReachableThroughPort(self, port):
        if port not in self.reachable_through_ports:
            self.reachable_through_ports.append(port)

    def addUniqueKnownIP(self, ip_address):
        self._updateIPsTimeout(ip_address)
        if ip_address not in self._knownIPsTimeout:
            self._knownIPsTimeout[ip_address] = datetime.datetime.now()

    def isIPKnown(self, ip_address):
        self._updateIPsTimeout(ip_address)
        return ip_address in self._knownIPsTimeout

    def getKnownIPsList(self):
        ip_list = []
        for ip in self._knownIPsTimeout:
            self._updateIPsTimeout(ip)
            if ip in self._knownIPsTimeout:
                ip_list.append(ip)
        return ip_list

    def _updateIPsTimeout(self, ip_address):
        if ip_address in self._knownIPsTimeout:
            now = datetime.datetime.now()
            if (now - self._knownIPsTimeout[ip_address]).seconds >= 1:
                del self._knownIPsTimeout[ip_address]
