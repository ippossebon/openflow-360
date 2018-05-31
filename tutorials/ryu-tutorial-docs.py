# Tutorial from http://ryu.readthedocs.io/en/latest/writing_ryu_app.html
# ryu-manager of-test.py

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0


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
        msg = ev.msg # object that represents a packet_in data structure
        dp = msg.datapath # object that represents a datapath (switch)

        # dp.ofproto and dp.ofproto_parser are objects that represent the
        # OpenFlow protocol that Ryu and the switch negotiated.
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

        ''' OFPActionOutput class is used with a packet_out message to specify a
            switch port that you want to send the packet out of. This application
            needs a switch to send out of all the ports so OFPP_FLOOD constant
            is used.

            OFPPacketOut class is used to build a packet_out message.
            If you call Datapath class's send_msg method with a OpenFlow
            message class object, Ryu builds and send the on-wire data format
            to the switch.
        '''
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions)
        dp.send_msg(out)
