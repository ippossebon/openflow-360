#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

        self.switches_learning_table = {
            "11:00:00:00:00:01": {
                "10.0.0.3": [], # interfaces pelas quais consegue alcançar o host
                "10.0.0.4": []
            },
            "11:00:00:00:00:02": {
                "10.0.0.5": [] # interfaces pelas quais consegue alcançar o host
            },
            "11:00:00:00:00:03": {
                "10.0.0.1": [], # interfaces pelas quais consegue alcançar o host
                "10.0.0.2": []
            }
        }

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

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)


        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignora pacotes LLDP (Link descovery)
            return

        dst_mac_address = eth.dst
        src_mac_address = eth.src
        datapath_id = datapath.id
        in_port = msg.in_port

        self.mac_to_port.setdefault(datapath_id, {})

        self.logger.info("packet in DATAPATH ID: %s src_mac_address: %s dst_mac_address: %s in_port: %s",
            datapath_id, src_mac_address, dst_mac_address, msg.in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[datapath_id][src_mac_address] = msg.in_port


        """ --- Shortest path --- """
        if src_mac_address not in self.net: #
            self.net.add_node(src_mac_address) # Add a node to the graph
            self.net.add_edge(src_mac_address, datapath_id) # Add a link from the node to it's edge switch
            # Add link from switch to node and make sure you are identifying the output port.
            self.net.add_edge(datapath_id, src_mac_address, port={'port':msg.in_port})

         # Se já conhece/sabe quem é o host de destino da mensagem, envia para a porta mapeada.
        if dst_mac_address in self.net:
            path = nx.shortest_path(self.net, src_mac_address, dst_mac_address) # get shortest path
            next = path[path.index(datapath_id)+1] # get next hop
            out_port = self.net[datapath_id][next]['port'] # get output port
        else:
            # If destination MAC is unknown then flood it
            out_port = ofproto.OFPP_FLOOD

        """ --- Fim do Shortest path --- """

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]

        # Instala fluxo no switch para evitar voltar ao controlador da próxima vez
        if out_port != ofproto.OFPP_FLOOD:
            self.add_flow(datapath, in_port, dst_mac_address, src_mac_address, actions)

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
        self.net.add_edge(src_dpid, dst_dpid, port={'port': src_port_no})
        # DownLink
        self.net.add_edge(dst_dpid, src_dpid, port={'port': dst_port_no})

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
            self.net.add_edge(dpid, src, port={'port':msg.in_port})

        if dst in self.net:
            path = nx.shortest_path(self.net, src, dst) # get shortest path
            next = path[path.index(dpid)+1] # get next hop
            out_port = self.net[dpid][next]['port'] # get output port
        else:
            # If destination MAC is unknown then flood it
            out_port = ofproto.OFPP_FLOOD
