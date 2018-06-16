from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import ethernet, ether_types, arp, packet, ipv4

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link

from GlobalARPEntry import GlobalARPEntry
from LearningTable import LearningTable

globalARPEntry = GlobalARPEntry()


class SwitchOFController (app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SwitchOFController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = []
        self.learning_table = LearningTable()


    def isLLDPPacket(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        return eth.ethertype == ether_types.ETH_TYPE_LLDP

    def isARPPacket(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        return eth.ethertype == ether_types.ETH_TYPE_ARP


    def forwardPacket(self, msg, port, buffer_id, actions):
        datapath = msg.datapath

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath = msg.datapath,
            in_port = msg.match['in_port'],
            buffer_id = buffer_id,
            actions = actions
        )#Generate the message
        datapath.send_msg(out) #Send the message to the switch

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
            self.handleARPPacket(ev)
        else:
            actLikeL2Learning(ev)


    def handleARPPacket(self, ev):
        if self.isARPRequest(ev):
            self.handleARPRequest(ev)
        else:
            self.handleARPReply(ev)

    def isARPRequest(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        arpPacket = pkt.get_protocol(arp.arp)

        return arpPacket.opcode == 1


    def handleARPRequest(self, ev):
        """
        Na primeira vez que o controlador tiver contato com um novo fluxo,
        obrigatoriamente, quem enviou este pacote foi o switch que está ligado
        diretamente com o host que enviou o pacote ARP. Isto é, tem conexão direta
        o host e o switch em questão e, portanto, last_mile = true. Caso contrário,
        será false.
        """
        msg = ev.msg
        datapath = msg.datapath
        pkt = packet.Packet(msg.data)
        arp_packet = pkt.get_protocol(arp.arp)

        requestor_mac = arp_packet.src_mac
        requested_ip = arp_packet.dst_ip
        in_port = msg.match['in_port']

        last_mile = globalARPEntry.isNewARPFlow(requestor_mac, requested_ip)

        # Atualiza tabela com as informações (se existirem)
        globalARPEntry.update(requestor_mac, requested_ip)

        if not self.learning_table.macIsKnown(requestor_mac):
            # Para este switch, é um host novo
            self.learnDataFromPacket(requestor_mac, in_port, last_mile)
            self.learning_table.appendKnownIPForMAC(requestor_mac, requested_ip)

            # Segue com o fluxo do pacote
            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
            self.forwardPacket(msg, in_port, msg.buffer_id, actions)

        elif not self.learning_table.isIPKnownForMAC(requestor_mac, requested_ip):
            # Este é um host já conhecido, fazendo um novo ARP Request
            self.learnDataFromPacket(requestor_mac, in_port, last_mile)
            self.learning_table.appendKnownIPForMAC(requestor_mac, requested_ip)

            # Segue com o fluxo do pacote
            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
            self.forwardPacket(msg, in_port, msg.buffer_id, actions)
        else:
            # Possivelmente, está recebendo um pacote ARP já conhecido (possível loop)
            if not self.learning_table.isLastMile(requestor_mac):
                # Se o request foi feito por um host que não tem ligação direta com o switch ??
                self.learnDataFromPacket(requestor_mac, in_port, last_mile)

            #self.dropPacket(packetIn) ?
            return


    def handleARPReply(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        pkt = packet.Packet(msg.data)
        arp_packet = pkt.get_protocol(arp.arp)

        requestor_mac = arp_packet.src_mac
        requested_ip = arp_packet.dst_ip
        in_port = msg.match['in_port']

        last_mile = globalARPEntry.isNewARPFlow(requestor_mac, requested_ip)

        # Atualiza tabela com as informações (se existirem)
        globalARPEntry.update(requestor_mac, requested_ip)

        self.learnDataFromPacket(requestor_mac, in_port, last_mile)

        destination_mac = arp_packet.dst_mac
        #out_port = self.learning_table.getAnyPortToReachHost(packet.dst, in_port)
        out_port = self.learning_table.getAnyPortToReachHost(destination_mac, in_port)

        # Switch envia ARP reply para destino na porta out_port

        actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
        self.forwardPacket(msg, out_port, msg.buffer_id, actions)


    def learnDataFromPacket(self, source_mac, in_port, last_mile = False):
        if self.learning_table.macIsKnown(source_mac):
            # É um host conhecido, vai acrescentar informações
            self.learning_table.appendReachableThroughPort(source_mac, in_port)

            if last_mile == False and self.learning_table.isLastMile(source_mac):
                last_mile = True

            self.learning_table.setLastMile(source_mac, last_mile)
        else:
            # É um novo host, vai criar entrada na tabela
            self.learning_table.createNewEntryWithProperties(source_mac, in_port, last_mile)


    def actLikeL2Learning(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)

        if self.learning_table.macIsKnown(destination_mac):
            # Decide caminho para destination_mac de acordo com a tabela
            out_port = self.learning_table.getAnyPortToReachHost(destination_mac, msg.in_port)
            self.forwardPacket(msg, out_port)
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

    """
    Instala fluxo no switch. Isto é, envia mensagem de FlowMod.

    """
    def add_flow(self, datapath, in_port, dst, src, actions):
        ofproto = datapath.ofproto

        match = datapath.ofproto_parser.OFPMatch(
            in_port=in_port,
            dl_dst=haddr_to_bin(dst),
            dl_src=haddr_to_bin(src)
        )

        idle_timeout = 1
        hard_timeout = 3
        if self.learningTable.isLastMile(destinationMAC):
            idle_timeout = 300
            hard_timeout = 600

        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath,
            match=match,
            cookie=0,
            command=ofproto.OFPFC_ADD,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            priority=ofproto.OFP_DEFAULT_PRIORITY,
            flags=ofproto.OFPFF_SEND_FLOW_REM,
            actions=actions
        )

        datapath.send_msg(mod)
