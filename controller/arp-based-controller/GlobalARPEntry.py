
class GlobalARPEntry (object):

    def __init__(self):
        self.global_ARP_entry = {}
        self.log.info("GlobalARPEntry initialized")

    def macExists(self, mac_address):
        return mac_address in self.global_ARP_entry

    def createNewEntryForMAC(self, mac_address):
        if self.macExists(mac_address):
            self.log.warning("createNewEntryForMAC called with existant MAC ADDRESS: " + str(mac_address))
            return
        else:
            self.global_ARP_entry[mac_address] = []

    def addUniqueIPForMAC(self, mac_address, ip_address):
        if not self.macExists(mac_address):
            self.log.error("addUniqueIPForMac called with non existant MAC ADDRESS: " + str(mac_address))
            return
        else:
            if ip_address not in self.global_ARP_entry[mac_address]:
                self.global_ARP_entry[mac_address].append(ip_address)

    def isIPKnownForMAC(self, mac_address, ip_address):
        # Indica se já sabemos o IP do host em questão
        return self.macExists(mac_address) and ip_address in self.global_ARP_entry[mac_address]

    def isNewARPFlow(self, arpPacket):
        requestor_mac = arpPacket.hwsrc
        requested_ip = arpPacket.protodst

        # Verifica se o pacote ARP é de um novo host ou se traz um novo IP para um host conhecido.
        is_new_host = not self.macExists(requestor_mac)
        host_has_mapped_ip = self.isIPKnownForMAC(requestor_mac, requested_ip)
        has_new_info = is_new_host or not host_has_mapped_ip

        return has_new_info

    def update(self, arpPacket):
        if self.isNewARPFlow(arpPacket):
            requestor_mac = arpPacket.hwsrc
            requested_ip = arpPacket.protodst
            if not self.macExists(requestor_mac):
                self.createNewEntryForMAC(requestor_mac)
            self.addUniqueIPForMAC(requestor_mac, requested_ip)
