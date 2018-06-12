#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController

class SingleSwitchTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')

        h1 = self.addHost('h1', mac="00:00:00:00:00:01", ip="10.0.0.1/12")
        h2 = self.addHost('h2', mac="00:00:00:00:00:02", ip="10.0.0.2/12")
        h3 = self.addHost('h3', mac="00:00:00:00:00:03", ip="10.0.0.3/12")
        h4 = self.addHost('h4', mac="00:00:00:00:00:04", ip="10.0.0.4/12")
        h5 = self.addHost('h5', mac="00:00:00:00:00:05", ip="10.0.0.5/12")

        self.addLink(h3, s1)
        self.addLink(h4, s1)

        self.addLink(h5, s2)

        self.addLink(h1, s3)
        self.addLink(h2, s3)

        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s1)


if __name__ == '__main__':
    setLogLevel('info')
    topo = SingleSwitchTopo()
    c1 = RemoteController('c1', ip='127.0.0.1')
    net = Mininet(topo=topo, controller=c1)
    net.start()
    #net.pingAll()
    CLI(net)
    net.stop()
