from HostProperties import HostProperties
import random

class LearningTable (object):

    def __init__(self):
        self.macMap = {}

    def getPropertiesForMAC(self, mac_address):
        if mac_address not in self.macMap:
            print("ERROR: Called getProperties for non existent MAC Address: ".join(mac_address))
            return None
        else:
            return self.macMap[mac_address]

    def macIsKnown(self, mac_address):
        return mac_address in self.macMap

    def createNewEntryForMAC(self, mac_address):
        if mac_address in self.macMap:
            print("ERROR: Called createNewEntry for existent MAC Address: ".join(mac_address))
        else:
            self.macMap[mac_address] = HostProperties()
        return self.getPropertiesForMAC(mac_address)

    def createNewEntryWithProperties(self, mac_address, reachable_through_port, last_mile):
        hostProperties = self.createNewEntryForMAC(mac_address)
        hostProperties.addUniqueReachableThroughPort(reachable_through_port)
        hostProperties.last_mile = last_mile

    def appendKnownIPForMAC(self, mac_address, ip_address):
        self.getPropertiesForMAC(mac_address).addUniqueKnownIP(ip_address)

    def appendReachableThroughPort(self, mac_address, port):
        self.getPropertiesForMAC(mac_address).addUniqueReachableThroughPort(port)

    def setLastMile(self, mac_address, last_mile):
        self.getPropertiesForMAC(mac_address).last_mile = last_mile

    def isIPKnownForMAC(self, mac_address, ip_address):
        return self.getPropertiesForMAC(mac_address).isIPKnown(ip_address)

    def isLastMile(self, mac_address):
        return self.getPropertiesForMAC(mac_address).last_mile

    def getCandidatePorts(self, mac_address, exclude_port):
        candidate_ports = list(self.getPropertiesForMAC(mac_address).reachable_through_ports)
        if len(candidate_ports) > 1 and exclude_port in candidate_ports:
            candidate_ports.remove(exclude_port)
        return candidate_ports

    def getFirstReachableThroughPort(self, mac_address, exclude_port):
        self.getPropertiesForMAC(mac_address).reachable_through_ports.rotate(1)
        return self.getCandidatePorts(mac_address, exclude_port)[0]

    def getRandomReachableThroughPort(self, mac_address, exclude_port):
        candidate_ports = self.getCandidatePorts(mac_address, exclude_port)
        return random.choice(candidate_ports)

    def getUnusedPortToHost(self, mac_address, exclude_port):
        candidate_ports = self.getCandidatePorts(mac_address, exclude_port)
        last_port = self.getPropertiesForMAC(mac_address).last_port
        if len(candidate_ports) > 1 and (last_port != None) and (last_port in candidate_ports):
            candidate_ports.remove(last_port)
        chosenPort = random.choice(candidate_ports)
        return chosenPort

    def getAnyPortToReachHost(self, mac_address, exclude_port):
        return self.getUnusedPortToHost(mac_address, exclude_port)

    def printTable(self):
        print('------------------------------')
        for item in self.macMap:
            print('* HOST: {0}'.format(item))
            print(self.macMap[item].printProperties())
        print('------------------------------')
