import json
import os
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

INTERVAL = 2  # seconds between measurements
STATS_FILE = '/tmp/link_load.json'

# (switch id, port number) -> link name, taken from our topology
LINKS = {
    (1, 2): "s1->s2", (2, 1): "s2->s1",
    (2, 2): "s2->s4", (4, 2): "s4->s2",
    (1, 3): "s1->s3", (3, 1): "s3->s1",
    (3, 2): "s3->s4", (4, 3): "s4->s3",
}


class LinkMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datapaths = {}
        self.prev_tx = {}
        self.link_load = {}
        hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                parser = dp.ofproto_parser
                req = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req)
            hub.sleep(INTERVAL)
            if self.link_load:
                line = " | ".join(f"{name} {mbps:5.2f}"
                                  for name, mbps in sorted(self.link_load.items()))
                self.logger.info("Mbps: %s", line)
                self._write_stats()

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        for stat in ev.msg.body:
            key = (dpid, stat.port_no)
            if key not in LINKS:
                continue
            prev = self.prev_tx.get(key)
            self.prev_tx[key] = stat.tx_bytes
            if prev is None:
                continue
            self.link_load[LINKS[key]] = (stat.tx_bytes - prev) * 8 / INTERVAL / 1e6

    def _write_stats(self):
        # write to a temp file then rename, so readers never see half a file
        tmp = STATS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.link_load, f)
        os.replace(tmp, STATS_FILE)
