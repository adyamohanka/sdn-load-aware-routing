import json
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
STATS_FILE = "/tmp/link_load.json"
CAPACITY = 10.0  # Mbps, each link in our topology

PAGE = """
<!doctype html>
<title>SDN Link Load</title>
<style>
  body { font-family: sans-serif; max-width: 560px; margin: 30px auto; }
  .row { margin: 10px 0; }
  .bar { background: #eee; height: 22px; border-radius: 4px; }
  .fill { background: #2a7de1; height: 100%; border-radius: 4px; transition: width .5s; }
  .hot { background: #e5484d; }
</style>
<h2>Live link load (Mbps)</h2>
<div id="links">waiting for data...</div>
<script>
const GROUPS = {
  "Path A (via s2)": ["s1->s2", "s2->s4"],
  "Path B (via s3)": ["s1->s3", "s3->s4"]
};
function color(pct) {
  return pct > 80 ? '#e5484d' : pct > 40 ? '#f5a524' : '#2fb344';
}
async function refresh() {
  const r = await fetch('/api/links');
  const d = await r.json();
  let html = '';
  for (const [title, names] of Object.entries(GROUPS)) {
    html += `<h3>${title}</h3>`;
    for (const n of names) {
      const v = d.links[n] || 0;
      const pct = Math.min(100, v / d.capacity * 100);
      html += `<div class="row">${n}: ${v.toFixed(2)} Mbps
        <div class="bar"><div class="fill"
        style="width:${pct}%;background:${color(pct)}"></div></div></div>`;
    }
  }
  document.getElementById('links').innerHTML = html;
}
setInterval(refresh, 1000);
refresh();
</script>
"""

@app.route("/")
def index():
    return render_template_string(PAGE)

@app.route("/api/links")
def links():
    try:
        with open(STATS_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return jsonify({"links": data, "capacity": CAPACITY})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
