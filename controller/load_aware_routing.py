import os
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import packet, ipv4, tcp, udp
from ryu.ofproto import ofproto_v1_3

H1, H2 = "10.0.0.1", "10.0.0.2"

# Each hop is (switch id, in port, out port), read off our topology.
PATHS = {
    "A": {  # via s2
        "fwd": [(1, 1, 2), (2, 1, 2), (4, 2, 1)],
        "rev": [(4, 1, 2), (2, 2, 1), (1, 2, 1)],
        "fwd_links": ["s1->s2", "s2->s4"],
        "rev_links": ["s4->s2", "s2->s1"],
    },
    "B": {  # via s3
        "fwd": [(1, 1, 3), (3, 1, 2), (4, 3, 1)],
        "rev": [(4, 1, 3), (3, 2, 1), (1, 3, 1)],
        "fwd_links": ["s1->s3", "s3->s4"],
        "rev_links": ["s4->s3", "s3->s1"],
    },
}

# Switch ports that belong to each path (host-facing ports are shared, so left out).
PATH_PORTS = {
    "A": {(1, 2), (2, 1), (2, 2), (4, 2)},
    "B": {(1, 3), (3, 1), (3, 2), (4, 3)},
}

RECENT_SECS = 4        # the monitor needs a moment to notice a new flow
RECENT_PENALTY = 5.0   # so each recent placement counts as ~5 Mbps
IDLE_TIMEOUT = 10      # a rule disappears after 10 s without traffic
BASELINE = os.environ.get("ROUTING_MODE") == "shortest"


class LoadAwareRouting(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}
        self.flow_path = {}    # flow -> "A" or "B"
        self.recent = []       # (time, path) of recent placements
        self.down_ports = set()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        self.datapaths[dp.id] = dp
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    def add_flow(self, dp, priority, match, actions, idle=0):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority, match=match,
                                      instructions=inst, idle_timeout=idle))

    def make_match(self, parser, flow):
        src, dst, proto, sport, dport = flow
        f = dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst, ip_proto=proto)
        if proto == 6:
            f.update(tcp_src=sport, tcp_dst=dport)
        elif proto == 17:
            f.update(udp_src=sport, udp_dst=dport)
        return parser.OFPMatch(**f)

    def path_is_down(self, name):
        return any(p in self.down_ports for p in PATH_PORTS[name])

    def choose_path(self, direction):
        if BASELINE:
            return "A", {"A": 0.0, "B": 0.0}
        now = time.time()
        self.recent = [(t, p) for t, p in self.recent if now - t < RECENT_SECS]
        mon = app_manager.lookup_service_brick('LinkMonitor')
        load = mon.link_load if mon else {}
        scores = {}
        for name, info in PATHS.items():
            if self.path_is_down(name):
                continue  # never pick a broken path
            measured = max(load.get(l, 0.0) for l in info[direction + "_links"])
            placed = sum(1 for _, p in self.recent if p == name)
            scores[name] = measured + RECENT_PENALTY * placed
        if not scores:
            return "A", {}
        best = min(scores, key=scores.get)
        self.recent.append((now, best))
        return best, scores

    def install_path(self, flow, direction, path):
        # last switch first, so the rules are ready before the packet arrives
        for dpid, _, out_port in reversed(PATHS[path][direction]):
            dp = self.datapaths.get(dpid)
            if dp is None:
                continue
            parser = dp.ofproto_parser
            match = self.make_match(parser, flow)
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(dp, 10, match, actions, IDLE_TIMEOUT)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        key = (dp.id, msg.desc.port_no)
        is_down = bool(msg.desc.state & ofp.OFPPS_LINK_DOWN) or msg.reason == ofp.OFPPR_DELETE
        was_down = key in self.down_ports
        if is_down:
            self.down_ports.add(key)
        else:
            self.down_ports.discard(key)
        if is_down == was_down:
            return
        self.logger.info("PORT s%s port %s is now %s", dp.id, key[1],
                         "DOWN" if is_down else "UP")
        if is_down and not BASELINE:
            self.reroute_flows()

    def reroute_flows(self):
        for flow, path in list(self.flow_path.items()):
            if not self.path_is_down(path):
                continue
            other = "B" if path == "A" else "A"
            if self.path_is_down(other):
                self.logger.warning("both paths are down, cannot reroute %s", flow)
                continue
            direction = "fwd" if flow[0] == H1 else "rev"
            self.flow_path[flow] = other
            self.install_path(flow, direction, other)
            self.logger.info("REROUTE %s:%s -> %s:%s moved path %s -> %s",
                             flow[0], flow[3], flow[1], flow[4], path, other)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        pkt = packet.Packet(msg.data)
        ip = pkt.get_protocol(ipv4.ipv4)
        if ip is None:
            return  # ARP, IPv6 and the rest are ignored
        if (ip.src, ip.dst) == (H1, H2):
            direction, other = "fwd", "rev"
        elif (ip.src, ip.dst) == (H2, H1):
            direction, other = "rev", "fwd"
        else:
            return

        sport = dport = 0
        t = pkt.get_protocol(tcp.tcp)
        u = pkt.get_protocol(udp.udp)
        l4 = t if t is not None else u
        if l4 is not None:
            sport, dport = l4.src_port, l4.dst_port
        flow = (ip.src, ip.dst, ip.proto, sport, dport)
        reverse = (ip.dst, ip.src, ip.proto, dport, sport)

        path = self.flow_path.get(flow)
        if path is None or (not BASELINE and self.path_is_down(path)):
            path, scores = self.choose_path(direction)
            self.flow_path[flow] = path
            self.flow_path[reverse] = path
            self.logger.info("NEW FLOW %s:%s -> %s:%s proto %s -> path %s  scores %s",
                             ip.src, sport, ip.dst, dport, ip.proto, path, scores)

        self.install_path(flow, direction, path)
        self.install_path(reverse, other, path)

        for dpid, _, out_port in PATHS[path][direction]:
            if dpid == dp.id:
                data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
                out = parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                          in_port=msg.match['in_port'],
                                          actions=[parser.OFPActionOutput(out_port)],
                                          data=data)
                dp.send_msg(out)
