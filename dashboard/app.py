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
async function refresh() {
  const r = await fetch('/api/links');
  const d = await r.json();
  let html = '';
  for (const [name, v] of Object.entries(d.links).sort()) {
    const pct = Math.min(100, v / d.capacity * 100);
    html += `<div class="row">${name}: ${v.toFixed(2)}
      <div class="bar"><div class="fill ${pct > 80 ? 'hot' : ''}"
      style="width:${pct}%"></div></div></div>`;
  }
  document.getElementById('links').innerHTML = html || 'no data yet';
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
