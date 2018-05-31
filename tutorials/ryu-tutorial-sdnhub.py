# Tutorial from http://sdnhub.org/tutorials/ryu/

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet


class Layer2Switch(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Layer2Switch, self).__init__(*args, **kwargs)

    ''' This is called when Ryu receives an OpenFlow packet_in message.
        The trick is 'set_ev_cls' decorator. This decorator tells Ryu when
        the decorated function should be called.

        Every time Ryu gets a packet_in message, EventOFPPacketIn is called.

        The second argument indicates the state of the switch. Probably, you
        want to ignore packet_in messages before the negotiation between Ryu
        and the switch finishes. Using 'MAIN_DISPATCHER' as the second argument
        means this function is called only after the negotiation completes.
    '''
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg               # Object representing a packet_in data structure.
        datapath = msg.datapath    # Switch Datapath ID
        ofproto = datapath.ofproto # OpenFlow Protocol version the entities negotiated. In our case OF1.3

        '''
        We can inspect the packet headers for several packet types: ARP, Ethernet,
        ICMP, IPv4, IPv6, MPLS, OSPF, LLDP, TCP, UDP. For set of packet types
        supported refer to https://github.com/osrg/ryu/tree/master/ryu/lib/packet
        '''
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        #Extract Ether header details
        dst = eth.dst
        src = eth.src

        # Similarly, the OFPPacketOut class can be used to build a
        # packet_out message with the required information (e.g.,
        # Datapath ID, associated actions etc)
        out = ofp_parser.OFPPacketOut(
            datapath=dp,
            in_port=msg.in_port,
            actions=actions
        )#Generate the message
        dp.send_msg(out) #Send the message to the switch

        '''
        Besides a PACKET_OUT, we can also perform a FLOW_MOD insertion into a switch.
        For this, we build the Match, Action, Instructions and generate the required
        Flow. Here is an example of how to create a match header where the in_port
        and eth_dst matches are extracted from the PACKET_IN:
        '''
        in_port = msg.match['in_port']
        # Get the destination ethernet address
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)

        # Creating an action list for the flow
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)] # Build the required action

        # Once the match rule and action list is formed, instructions are created as follows:
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        # Given the above code, a Flow can be generated and added to a particular switch.
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, match=match, instructions=inst)
        datapath.send_msg(mod)

        
