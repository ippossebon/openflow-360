from GlobalARPEntry import GlobalARPEntry
from LearningTable import LearningTable

globalARPEntry = GlobalARPEntry()


class SwitchOFController (app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = []
        self.learning_table = LearningTable()


    def isLLDPPacket(self, ev):
        return eth.ethertype == ether_types.ETH_TYPE_LLDP

    def isARPPacket(self, ev):
        return eth.ethertype == ether_types.ETH_TYPE_ARP


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        print('>>> Packet In message')

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)


        if self.isLLDPPacket(ev):
            # ignora pacotes LLDP (Link descovery)
            return

        if self.isARPPacket(ev):
            has_new_info = self.handleARPPacket(ev)

            # Se nada de novo pode ser aprendido com um ARP Request, o pacote é dropado
            if not has_new_info:
                self.logger.info('> Sem novas infos com este pacote ARP')
                return
            else:
                self.logger.info('> Pacote ARP trouxe novas infos')
        else:
            actLikeL2Learning(ev)


    def handleARPPacket(self, ev):
        if self.isARPRequest(ev):
            self.handleARPRequest(ev)
        else:
            self.handleARPReply(ev)

    def isARPRequest(self, ev):
        pass

    def handleARPRequest(self, ev):
        # recebe packet e packetIn

        # last_mile indica se o pacote trouxe alguma informação nova
        last_mile = globalARPEntry.isNewARPFlow(ev)

        # Atualiza tabela com as informações (se existirem)
        globalARPEntry.update(arp_packet)

        source_mac = arp_packet.source
        destination_ip = arp_packet.destination_ip

        if not self.learning_table.macIsKnown(source_mac):
            # Para este switch, é um host novo
            self.learnDataFromPacket(packet, packetIn, last_mile)
            self.learning_table.appendKnownIPForMAC(source_mac, destination_ip)

            self.resendPacket(packetIn, of.OFPP_ALL) # por que precisamos reenviar?

        elif not self.learning_table.isIPKnownForMAC(source_mac, destination_ip):
            # Este é um host já conhecido, fazendo um novo ARP Request
            self.learnDataFromPacket(packet, packetIn, last_mile)
            self.learning_table.appendKnownIPForMAC(source_mac, destination_ip)

            self.resendPacket(packetIn, of.OFPP_ALL) # por que precisamos reenviar?

        else:
            # Possivelmente, está recebendo um pacote ARP já conhecido (possível loop)
            if not self.learning_table.isLastMile(source_mac):
                # Se o request foi feito por um host que não tem ligação direta com o switch ??
                self.learnDataFromPacket(packet, packetIn, last_mile)

            self.dropPacket(packetIn)


    def handleARPReply(self, ev):
        # recebe packet e packetIn
        last_mile = globalARPEntry.isNewARPFlow(arp_packet) # ???

        globalARPEntry.update(arp_packet)
        self.learnDataFromPacket(packet, packetIn, last_mile)

        out_port = self.learning_table.getAnyPortToReachHost(packet.dst, packetIn.in_port)
        # Switch envia ARP reply para destino na porta out_port

        self.resendPacket(packet_in, out_port) # ??


    def learnDataFromPacket(self, packet, packetIn, last_mile = False):
        source_mac = packet.src

        if self.learning_table.macIsKnown(source_mac):
            # É um host conhecido, vai acrescentar informações
            self.learning_table.appendReachableThroughPort(source_mac, packetIn.in_port)

            if last_mile == False and self.learning_table.isLastMile(source_mac):
                last_mile = True

            self.learning_table.setLastMile(source_mac, last_mile)
        else:
            # É um novo host, vai criar entrada na tabela
            self.learning_table.createNewEntryWithProperties(source_mac, packetIn.in_port, last_mile)

    def actLikeL2Learning(self, packet, packetIn):

        if self.learning_table.macIsKnown(destination_mac):
            # Decide caminho para destination_mac de acordo com a tabela
            out_port = self.learning_table.getAnyPortToReachHost(destination_mac, packetIn.in_port)
            self.resendPacket(packetIn, out_port)
            self.installForwardingFlow(packet.src, destination_mac, out_port)
        else:
            print('Erro! Não conhece o host')


    def installForwardingFlow(self, sourceMAC, destinationMAC, outPort):
        log.info("Switch ID "+self.switchID+" >>> installing forwarding flow...")
        flowModMessage = of.ofp_flow_mod()
        if self.learningTable.isLastMile(destinationMAC):
            flowModMessage.idle_timeout = 300
            flowModMessage.hard_timeout = 600
        else:
            flowModMessage.idle_timeout = 1
            flowModMessage.hard_timeout = 3
        flowModMessage.match.dl_src = sourceMAC
        flowModMessage.match.dl_dst = destinationMAC
        flowModMessage.actions.append(of.ofp_action_output(port=outPort))
        self.connection.send(flowModMessage)
