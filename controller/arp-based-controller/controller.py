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
        # A chave do dicionário é o switch_id. Cada switch tem uma learning table associada
        self.learning_tables = {}

        # Para monitoramento
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.switch_port_statistics = {}


    def isLLDPPacket(self, ev):
        msg = ev.msg
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        return eth.ethertype == ether_types.ETH_TYPE_LLDP

    def isARPPacket(self, ev):
        msg = ev.msg
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
        )
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

        # Ignora pacotes LLDP (Link descovery)
        if self.isLLDPPacket(ev):
            return

        if self.isARPPacket(ev):
            self.handleARPPacket(ev)
        else:
            self.actLikeL2Learning(ev)


    def handleARPPacket(self, ev):
        if self.isARPRequest(ev):
            self.handleARPRequest(ev)
        else:
            self.handleARPReply(ev)


    def isARPRequest(self, ev):
        msg = ev.msg
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
        switch_id = datapath.id
        pkt = packet.Packet(msg.data)
        arp_packet = pkt.get_protocol(arp.arp)

        requestor_mac = arp_packet.src_mac
        requested_ip = arp_packet.dst_ip
        in_port = msg.match['in_port']

        last_mile = globalARPEntry.isNewARPFlow(requestor_mac, requested_ip)

        # Assumption: a primeira vez que um switch entrar em contato com o
        # controlador, será por causa de um ARP request/reply
        if str(switch_id) not in self.learning_tables:
            # Inicializa lerning table do switch
            self.learning_tables[str(switch_id)] = LearningTable()

        globalARPEntry.update(requestor_mac, requested_ip)

        print('[handleARPRequest] Host {0} querendo saber quem tem o IP {1}'.format(requestor_mac, requested_ip))

        if not self.learning_tables[str(switch_id)].macIsKnown(requestor_mac):
            # Para este switch, é um host novo
            print('[handleARPRequest]: para o switch {0} eh um host novo.'.format(switch_id))

            self.learnDataFromPacket(switch_id, requestor_mac, in_port, last_mile)

            self.learning_tables[str(switch_id)].appendKnownIPForMAC(requestor_mac, requested_ip)

            # Segue com o fluxo do pacote
            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
            self.forwardPacket(msg, in_port, msg.buffer_id, actions)

        elif not self.learning_tables[str(switch_id)].isIPKnownForMAC(requestor_mac, requested_ip):
            # Este é um host já conhecido, fazendo um novo ARP Request
            print('[handleARPRequest]: para o switch {0} eh um host conhecido fazendo um ARP.'.format(switch_id))

            self.learnDataFromPacket(switch_id, requestor_mac, in_port, last_mile)
            self.learning_tables[str(switch_id)].appendKnownIPForMAC(requestor_mac, requested_ip)

            # Segue com o fluxo do pacote
            actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_FLOOD)]
            self.forwardPacket(msg, in_port, msg.buffer_id, actions)
        else:
            # Possivelmente, está recebendo um pacote ARP já conhecido (possível loop)
            if not self.learning_tables[str(switch_id)].isLastMile(requestor_mac):
                # Se o request foi feito por um host que não tem ligação direta com o switch
                self.learnDataFromPacket(switch_id, requestor_mac, in_port, last_mile)
            print('[handleARPRequest]: Dropa pacote')
            return


    def handleARPReply(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        switch_id = datapath.id
        pkt = packet.Packet(msg.data)
        arp_packet = pkt.get_protocol(arp.arp)
        in_port = msg.match['in_port']

        arp_reply_sender_mac = arp_packet.src_mac
        arp_reply_sender_ip = arp_packet.src_ip

        arp_reply_destination_mac = arp_packet.dst_mac
        arp_reply_destination_ip = arp_packet.dst_ip
        last_mile = globalARPEntry.isNewARPFlow(arp_reply_sender_mac, arp_reply_destination_ip)

        print('>>> ARP REPLY do host {0} para {1}'.format(
            arp_reply_sender_mac, arp_reply_destination_mac))

        # Assumption: a primeira vez que um switch entrar em contato com o
        # controlador, será por causa de um ARP request/reply
        if str(switch_id) not in self.learning_tables:
            # Inicializa lerning table do switch
            self.learning_tables[str(switch_id)] = LearningTable()

        # Atualiza tabela com as informações (se existirem)
        globalARPEntry.update(arp_reply_sender_mac, arp_reply_destination_ip)

        self.learnDataFromPacket(switch_id, arp_reply_sender_mac, in_port, last_mile)

        out_port = self.learning_tables[str(switch_id)].getFirstReachableThroughPort(arp_reply_destination_mac, in_port)

        # Switch envia ARP reply para destino na porta out_port
        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        self.forwardPacket(msg, out_port, msg.buffer_id, actions)


    def learnDataFromPacket(self, switch_id, source_mac, in_port, last_mile = False):
        if self.learning_tables[str(switch_id)].macIsKnown(source_mac):
            # É um host conhecido, vai acrescentar informações
            self.learning_tables[str(switch_id)].appendReachableThroughPort(source_mac, in_port)

            if last_mile == False and self.learning_tables[str(switch_id)].isLastMile(source_mac):
                last_mile = True

            self.learning_tables[str(switch_id)].setLastMile(source_mac, last_mile)
        else:
            # É um novo host, vai criar entrada na tabela
            self.learning_tables[str(switch_id)].createNewEntryWithProperties(source_mac, in_port, last_mile)


    def actLikeL2Learning(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        switch_id = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        destination_mac = eth.dst
        source_mac = eth.src

        if self.learning_tables[str(switch_id)].macIsKnown(destination_mac):
            # Decide caminho para destination_mac de acordo com a tabela
            out_port = self.learning_tables[str(switch_id)].getFirstReachableThroughPort(destination_mac, in_port)

            print('[actLikeL2Learning] Switch {0} vai mandar pacote para {1} via porta {2}'.format(
                switch_id, destination_mac, out_port))

            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            self.forwardPacket(msg, out_port, msg.buffer_id, actions)

            self.addFlow(datapath, in_port, destination_mac, source_mac, actions)
        else:
            print('Erro! Nao conhece o host')


    def choosePortBasedOnStatistics(self, datapath):
        #TODO
        self.switch_port_statistics
        pass


    def printLearningTables(self):
        for switch_id in self.learning_tables:
            print('Table {0}'.format(switch_id))
            self.learning_tables[switch_id].printTable()


    """ Instala fluxo no switch. Isto é, envia mensagem de FlowMod. """
    def addFlow(self, datapath, in_port, dst, src, actions):
        switch_id = datapath.id
        ofproto = datapath.ofproto

        match = datapath.ofproto_parser.OFPMatch(in_port=in_port, eth_dst=dst)
        inst = [datapath.ofproto_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        idle_timeout = 1
        hard_timeout = 3

        if self.learning_tables[str(switch_id)].isLastMile(dst):
            idle_timeout = 300 # 5 minutos
            hard_timeout = 600 # 10 minutos

        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath,
            match=match,
            command=ofproto.OFPFC_ADD,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            priority=ofproto.OFP_DEFAULT_PRIORITY,
            instructions=inst
        )

        datapath.send_msg(mod)

    """----------------------- Monitoramento de status -----------------------"""
    def monitor(self):
        while True:
            for dp in self.datapaths.values():
                self.requestStatus(dp)
            hub.sleep(10)

    def requestStatus(self, datapath):
        print('Send status request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def portStatusReplyHandler(self, ev):
        body = ev.msg.body

        print('[portStatusReplyHandler] datapath         port     '
                         'rx-pkts  rx-bytes rx-error '
                         'tx-pkts  tx-bytes tx-error')
        print('[portStatusReplyHandler] ---------------- -------- '
                         '-------- -------- -------- '
                         '-------- -------- --------')
        for stat in sorted(body, key=attrgetter('port_no')):
            print('[portStatusReplyHandler] %016x %8x %8d %8d %8d %8d %8d %8d',
                             ev.msg.datapath.id, stat.port_no,
                             stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                             stat.tx_packets, stat.tx_bytes, stat.tx_errors)


    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def stateChangeHandler(self, ev):
        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                print('[stateChangeHandler] Register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                print('[stateChangeHandler] Unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
