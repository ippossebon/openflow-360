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
        #print('[macIsKnown] para MAC = {0}'.format(mac_address))
        self.printTable()
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
        #print('[getCandidatePorts] MAC = {0}, exclude_port = {1}'.format(mac_address, exclude_port))
        self.printTable()

        candidate_ports = list(self.getPropertiesForMAC(mac_address).reachable_through_ports)
        if len(candidate_ports) > 1 and exclude_port in candidate_ports:
            candidate_ports.remove(exclude_port)
        return candidate_ports

    # Round Robin
    def getFirstReachableThroughPort(self, mac_address, exclude_port):
        # Coloca a primeira porta (utilizada na última chamada) na última posição da lista
        self.getPropertiesForMAC(mac_address).reachable_through_ports.rotate(1)
        return self.getCandidatePorts(mac_address, exclude_port)[0]

    # Escolha aleatória
    def getRandomReachableThroughPort(self, mac_address, exclude_port):
        candidate_ports = self.getCandidatePorts(mac_address, exclude_port)
        return random.choice(candidate_ports)

    def getUnusedPortToHost(self, mac_address, exclude_port):
        candidate_ports = self.getCandidatePorts(mac_address, exclude_port)
        last_port = self.getPropertiesForMAC(mac_address).last_port

        # Se existem portas candidatas, e last_port foi setada, eu removo a porta que foi usada por ultimo.
        if len(candidate_ports) > 1 and (last_port != None) and (last_port in candidate_ports):
            candidate_ports.remove(last_port)
        chosenPort = random.choice(candidate_ports)
        return chosenPort

    # Pega qualquer porta que nao tenha sido usada anteriormente.
    # Round robin + escolhaaleatória
    def getAnyPortToReachHost(self, mac_address, exclude_port):
        return self.getUnusedPortToHost(mac_address, exclude_port)

    def printTable(self):
        print('------------------------------')
        for item in self.macMap:
            print('* HOST: {0}'.format(item))
            print(self.macMap[item].printProperties())
        print('------------------------------')
