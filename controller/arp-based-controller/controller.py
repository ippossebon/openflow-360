from GlobalARPEntry import GlobalARPEntry
from LearningTable import LearningTable

globalARPEntry = GlobalARPEntry()


class SwitchOFController (app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = []
        self.learningTable = LearningTable()


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        print('>>> Packet In message')

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)


        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignora pacotes LLDP (Link descovery)
            return

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            has_new_info = self.handleARPPacket(ev)

            # Se nada de novo pode ser aprendido com um ARP Request, o pacote é dropado
            if not has_new_info:
                self.logger.info('> Sem novas infos com este pacote ARP')
                return
            else:
                self.logger.info('> Pacote ARP trouxe novas infos')
        else:
            actLikeL2Learning(ev)
