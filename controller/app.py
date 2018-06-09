# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An OpenFlow 1.0 L2 learning switch implementation.

Isadora Possebon
"""

# run: ryu-manager sp.py --observe-links

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import ethernet, ether_types, arp, packet, ipv4

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link

import networkx as nx

'''
switches_arp_table:
{
    1: {
        in_ports: [],
        ip_adds: [],
        last_mile: boolean
    },
    2: {
        interfaces: [],
        ip_adds: [],
        last_mile: boolean
    }
}

'''

class SimpleSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switches = []

        self.switches_arp_table = {}

        self.net=nx.DiGraph()
        self.stp = nx.Graph()


    """
    Instala fluxo no switch. Isto é, envia mensagem de FlowMod.

    """
    def add_flow(self, datapath, in_port, dst, src, actions):
        ofproto = datapath.ofproto

        match = datapath.ofproto_parser.OFPMatch(
            in_port=in_port,
            dl_dst=haddr_to_bin(dst), dl_src=haddr_to_bin(src))

        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, match=match, cookie=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=ofproto.OFP_DEFAULT_PRIORITY,
            flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)

        datapath.send_msg(mod)



    def arp_packet_in(self, ev):
        ''' Para cada host descoberto na rede, são armazenadas as seguintes informações:
            ○ Interfaces pelas é possível alcançá-lo
            ○ Endereços IP conhecidos (que estão na tabela ARP do host)
            ○ Última milha (booleano), indicando se o host está conectado diretamente ao
            switch em questão.

            Quando um novo ARP chega em um switch, essa tabela é consultada e
            complementada com informações novas.
            ○ Esse comportamento garante que ARP Requests não sejam reencaminhados infinitamente
            ● Entradas nessa tabela são gerenciadas por um tempo de timeout. Quando esse tempo é excedido, a entrada é deletada.
        '''
        switch = ev.switch
        self.switches.append(switch.dp)
        dpid = switch.dp.id
        in_port = ev.msg.match['in_port']

        ip_packet = pkt.get_protocol(ipv4.ipv4)
        src_ip_address = ip_packet.src
        has_new_info = False

        if not switches_arp_table.has_key(dpid):
            # Inicializa informações do switch
            self.switches_arp_table[dpid] = {}
            self.switches_arp_table[dpid]['in_ports'] = []
            self.switches_arp_table[dpid]['ip_addresses'] = []
            self.switches_arp_table[dpid]['direct_connection'] = True # indica se o host está conectado diretamente ao switch
            has_new_info = True

        # Preenche a tabela com as informações
        if in_port not in self.switches_arp_table[dpid]['in_ports']:
            self.switches_arp_table[dpid]['in_ports'].append(in_port)
            has_new_info = True

        if src_ip_address not in self.switches_arp_table[dpid]['ip_addresses']:
            src_ip_address not in self.switches_arp_table[dpid]['ip_addresses'].append(src_ip_address)
            has_new_info = True

        # TODO: rever..
        self.switches_arp_table[dpid]['direct_connection'] = True

        return has_new_info

    """
    Lógica da aplicação: o que acontece cada vez que um pacote chega ao controlador?

    > Se chegou ao controlador, é porque a sua rota não é conhecida. Isto é, dados
    endereços de origem e destino, não se sabe para qual porta o switch em questão
    deve encaminhar o pacote.


    """
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        print('>>> Packet In message')

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignora pacotes LLDP (Link descovery)
            return


        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            has_new_info = self.arp_packet_in(ev)

            # Se nada de novo pode ser aprendido com um ARP Request, o pacote é dropado
            if not has_new_info:
                return


        dst_mac_address = eth.dst
        src_mac_address = eth.src
        datapath_id = datapath.id

        self.mac_to_port.setdefault(datapath_id, {})

        self.logger.info("packet in %s %s %s %s", datapath_id, src_mac_address, dst_mac_address, msg.in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[datapath_id][src_mac_address] = msg.in_port


        """ --- Shortest path --- """
        if src not in self.net: #
            self.net.add_node(src) # Add a node to the graph
            self.net.add_edge(src, dpid) # Add a link from the node to it's edge switch
            # Add link from switch to node and make sure you are identifying the output port.
            self.net.add_edge(dpid, src, {'port':msg.in_port})

         # Se já conhece/sabe quem é o host de destino da mensagem, envia para a porta mapeada.
        if dst in self.net:
            path = nx.shortest_path(self.net, src, dst) # get shortest path
            next = path[path.index(dpid)+1] # get next hop
            out_port = self.net[dpid][next]['port'] # get output port
        else:
            # If destination MAC is unknown then flood it
            out_port = ofproto.OFPP_FLOOD

        """ --- Fim do Shortest path --- """

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]

        # Instala fluxo no switch para evitar voltar ao controlador da próxima vez
        if out_port != ofproto.OFPP_FLOOD:
            self.add_flow(datapath, msg.in_port, dst_mac_address, src_mac_address, actions)

        # o que isso faz??????
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        # Envia os dados pela porta de saída do switch em questão.
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=data)
        datapath.send_msg(out)


    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no

        ofproto = msg.datapath.ofproto
        if reason == ofproto.OFPPR_ADD:
            self.logger.info("port added %s", port_no)
        elif reason == ofproto.OFPPR_DELETE:
            self.logger.info("port deleted %s", port_no)
        elif reason == ofproto.OFPPR_MODIFY:
            self.logger.info("port modified %s", port_no)
        else:
            self.logger.info("Illeagal port state %s %s", port_no, reason)


    # Network topology #
    """
    The event EventSwitchEnter will trigger the activation of get_topology_data().
    Next we call get_switch() to get the list of objects Switch, and get_link()
    to get the list of objects Link. This objects are defined in the
    topology.switches file. Then, we build a list with all the switches ([switches])
    and next a list with all the links [(srcNode, dstNode, port)]. Notice that
    we also get the port from the source node that arrives at the destination
    node, as that information will be necessary later during the forwarding step.
    """
    @set_ev_cls(event.EventSwitchEnter)
    def add_switch(self, ev):
        switch = ev.switch
        self.switches.append(switch.dp)
        dpid = switch.dp.id

        # Adding switch node
        if dpid == 0:
            self.net.add_node('0', n_type='switch', has_host='false')
        else:
            self.net.add_node(dpid, n_type='switch', has_host='false')


    @set_ev_cls(event.EventLinkAdd, MAIN_DISPATCHER)
    def link_add_handler(self, ev):
        link = ev.link
        src_dpid = link.src.dpid
        dst_dpid = link.dst.dpid
        src_port_no = link.src.port_no
        dst_port_no = link.dst.port_no

        # Adding a edge from source datapath to destination datapath
        # UpLink
        self.net.add_edge(src_dpid, dst_dpid, {'port': src_port_no})
        # DownLink
        self.net.add_edge(dst_dpid, src_dpid, {'port': dst_port_no})

    """
    * Shortest Path forwarding
    If source MAC is unknown then learn it
    If destination MAC is unknown then flood it.
    If destination MAC is known then:
    get shortest path
    get next hop in path
    get output port for next hop
    """
    def shortest_path():
        if src not in self.net: # Learn it
            self.net.add_node(src) # Add a node to the graph
            self.net.add_edge(src, dpid) # Add a link from the node to it's edge switch
            # Add link from switch to node and make sure you are identifying the output port.
            self.net.add_edge(dpid, src, {'port':msg.in_port})

        if dst in self.net:
            path = nx.shortest_path(self.net, src, dst) # get shortest path
            next = path[path.index(dpid)+1] # get next hop
            out_port = self.net[dpid][next]['port'] # get output port
        else:
            # If destination MAC is unknown then flood it
            out_port = ofproto.OFPP_FLOOD
