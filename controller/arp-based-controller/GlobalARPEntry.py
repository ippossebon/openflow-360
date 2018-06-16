
class GlobalARPEntry (object):

    def __init__(self):
        self.global_ARP_entry = {}

    def macExists(self, mac_address):
        return mac_address in self.global_ARP_entry

    def createNewEntryForMAC(self, mac_address):
        if self.macExists(mac_address):
            print("createNewEntryForMAC called with existant MAC ADDRESS: " + str(mac_address))
            return
        else:
            self.global_ARP_entry[mac_address] = []

    def addUniqueIPForMAC(self, mac_address, ip_address):
        if not self.macExists(mac_address):
            print("addUniqueIPForMac called with non existant MAC ADDRESS: " + str(mac_address))
            return
        else:
            if ip_address not in self.global_ARP_entry[mac_address]:
                self.global_ARP_entry[mac_address].append(ip_address)

    def isIPKnownForMAC(self, mac_address, ip_address):
        # Indica se já sabemos o IP do host em questão
        return self.macExists(mac_address) and ip_address in self.global_ARP_entry[mac_address]


    """ Indica se o pacote em questão é de um novo flow """
    def isNewARPFlow(self, requestor_mac, requested_ip):
        # Verifica se o pacote ARP é de host conhecido ou se o pacote traz o IP de um MAC mapeado
        is_new_host = not self.macExists(requestor_mac)
        host_has_mapped_ip = self.isIPKnownForMAC(requestor_mac, requested_ip)
        is_new_arp_flow = is_new_host or not host_has_mapped_ip

        return is_new_arp_flow

    def update(self, requestor_mac, requested_ip):
        if self.isNewARPFlow(requestor_mac, requested_ip):
            if not self.macExists(requestor_mac):
                self.createNewEntryForMAC(requestor_mac)
            self.addUniqueIPForMAC(requestor_mac, requested_ip)
