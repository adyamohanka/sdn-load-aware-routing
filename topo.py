from functools import partial
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI

def build():
    net = Mininet(
        controller=RemoteController,
        switch=partial(OVSSwitch, protocols='OpenFlow13'),
        link=TCLink,
    )

    net.addController('c0', ip='127.0.0.1', port=6653)

    h1 = net.addHost('h1')
    h2 = net.addHost('h2')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')

    net.addLink(h1, s1)
    net.addLink(h2, s4)

    # Path A: s1 - s2 - s4
    net.addLink(s1, s2, bw=10)
    net.addLink(s2, s4, bw=10)
    # Path B: s1 - s3 - s4
    net.addLink(s1, s3, bw=10)
    net.addLink(s3, s4, bw=10)

    net.start()
    net.staticArp()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    build()
