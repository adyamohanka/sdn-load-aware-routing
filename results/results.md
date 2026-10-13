# Results: two simultaneous TCP flows h1 -> h2 (iperf, 60 s, 10 Mbps links)

| Routing | Flow 1 | Flow 2 | Total |
|---|---|---|---|
| Baseline (fixed shortest path) | 4.50 Mbits/s | 4.58 Mbits/s | 8.99 Mbits/s |
| Load-aware | 9.10 Mbits/s | 9.10 Mbits/s | 18.1 Mbits/s |

Single run per mode so far.

## Link-failure recovery
Single flow (ICMP ping every 0.1 s, 300 pings over 30 s). Link s1-s2 taken down at about 10 s.

| Metric | Result |
|---|---|
| Pings sent / received | 300 / 300 |
| Packet loss | 0% |
| Detected outage | under 0.1 s (limit of the 0.1 s ping interval) |

Controller log showed PORT DOWN followed immediately by REROUTE path A -> B.
One run so far.
