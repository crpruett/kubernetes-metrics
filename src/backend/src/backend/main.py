from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from kubernetes import client, config
from kubernetes.config import ConfigException
from kubernetes.client.exceptions import ApiException
from datetime import datetime

app = FastAPI(title="Kubernetes Metrics Dashboard")

core_v1 = None
mode = "mock"

# ---- Kubernetes config detection ----
try:
    config.load_incluster_config()
    core_v1 = client.CoreV1Api()
    mode = "kubernetes"
except ConfigException:
    try:
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
        mode = "local"
    except ConfigException:
        core_v1 = None
        mode = "mock"


# ---- API: metrics ----
@app.get("/")
def metrics():
    # Always return something
    if core_v1 is None:
        return {
            "mode": mode,
            "cluster": {
                "nodes": 0,
                "pods": 0,
                "namespaces": 0,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    try:
        nodes = core_v1.list_node().items
        pods = core_v1.list_pod_for_all_namespaces().items
        namespaces = core_v1.list_namespace().items

        return {
            "mode": mode,
            "cluster": {
                "nodes": len(nodes),
                "pods": len(pods),
                "namespaces": len(namespaces),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except ApiException as e:
        return {
            "mode": "kubernetes-error",
            "error": {
                "status": e.status,
                "reason": e.reason,
                "body": e.body,
            },
        }

    except Exception as e:
        return {
            "mode": "unexpected-error",
            "error": str(e),
        }


# ---- UI: simple frontend ----
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Cat DevOps Dashboard</title>
    <style>
      :root{
        --bg:#0b0f14; --card:#111826; --muted:#92a4b8; --fg:#e8eef6;
        --border:#1f2a3a; --ok:#30d158; --warn:#ffd60a; --bad:#ff453a;
        --accent:#5aa7ff;
        --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      }
      body{ margin:0; background:var(--bg); color:var(--fg); font-family:var(--sans); }
      header{ padding:28px 28px 10px; border-bottom:1px solid var(--border); }
      h1{ margin:0; font-size:20px; letter-spacing:.4px; }
      .sub{ margin-top:6px; color:var(--muted); font-size:13px; }
      main{ padding:22px 28px 40px; max-width:1100px; }
      .grid{ display:grid; grid-template-columns:repeat(12, 1fr); gap:14px; }
      .card{
        grid-column: span 4;
        background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,0));
        border:1px solid var(--border);
        border-radius:12px;
        padding:16px;
        min-height:96px;
      }
      .card.wide{ grid-column: span 12; }
      .label{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.9px; }
      .value{ margin-top:10px; font-size:30px; font-weight:600; }
      .row{ display:flex; align-items:center; justify-content:space-between; gap:12px; }
      .pill{
        font-family:var(--mono);
        font-size:12px;
        color:var(--muted);
        border:1px solid var(--border);
        padding:6px 10px;
        border-radius:999px;
        white-space:nowrap;
      }
      .status{ display:inline-flex; align-items:center; gap:8px; font-family:var(--mono); font-size:12px; }
      .dot{ width:9px; height:9px; border-radius:50%; background:var(--warn); box-shadow:0 0 0 3px rgba(255,214,10,.10); }
      .dot.ok{ background:var(--ok); box-shadow:0 0 0 3px rgba(48,209,88,.10); }
      .dot.bad{ background:var(--bad); box-shadow:0 0 0 3px rgba(255,69,58,.10); }
      pre{ margin:0; font-family:var(--mono); font-size:12px; color:var(--muted); overflow:auto; }
      a{ color:var(--accent); text-decoration:none; }
      a:hover{ text-decoration:underline; }
      @media (max-width: 900px){
        .card{ grid-column: span 12; }
      }
      .footer{ margin-top:18px; color:var(--muted); font-size:12px; }
      .error{ color:var(--bad); font-family:var(--mono); font-size:12px; }
    </style>
  </head>
  <body>
    <header>
      <div class="row">
        <div>
          <h1>Cat DevOps Dashboard</h1>
          <div class="sub">Kubernetes metrics + operational status</div>
        </div>
        <div class="pill" id="apiTarget">API: (not set)</div>
      </div>
    </header>

    <main>
      <div class="grid">
        <div class="card">
          <div class="row">
            <div class="label">Nodes</div>
            <div class="status"><span class="dot" id="dotNodes"></span><span id="mode">mode</span></div>
          </div>
          <div class="value" id="nodes">—</div>
        </div>

        <div class="card">
          <div class="label">Pods</div>
          <div class="value" id="pods">—</div>
        </div>

        <div class="card">
          <div class="label">Namespaces</div>
          <div class="value" id="namespaces">—</div>
        </div>

        <div class="card wide">
          <div class="row">
            <div class="label">Raw payload</div>
            <div class="pill" id="updated">Updated: —</div>
          </div>
          <div style="margin-top:12px;">
            <div id="err" class="error" style="display:none;"></div>
            <pre id="raw">{}</pre>
          </div>
          <div class="footer">
            Tip: set <span class="pill">API_BASE</span> to point at the backend (e.g., <span class="pill">/api</span> behind a reverse proxy).
          </div>
        </div>
      </div>
    </main>

    <script>
      // In production you typically inject this at build/deploy time.
      // For now, default to same-origin "/".
      const API_BASE = (window.API_BASE || "").trim();      // can be set by a small config script
      const METRICS_URL = (API_BASE ? API_BASE.replace(/\/$/, "") : "") + "/";

      document.getElementById("apiTarget").textContent = "API: " + (API_BASE || "(same origin)");

      function setDot(ok, bad){
        const dot = document.getElementById("dotNodes");
        dot.classList.remove("ok","bad");
        if (bad) dot.classList.add("bad");
        else if (ok) dot.classList.add("ok");
      }

      async function load() {
        const err = document.getElementById("err");
        try {
          const res = await fetch(METRICS_URL, { cache: "no-store" });
          const data = await res.json();

          document.getElementById("raw").textContent = JSON.stringify(data, null, 2);

          if (!res.ok || !data || !data.cluster) {
            err.style.display = "block";
            err.textContent = "Backend returned an error or unexpected payload.";
            setDot(false, true);
            return;
          }

          err.style.display = "none";
          document.getElementById("mode").textContent = data.mode || "unknown";
          document.getElementById("nodes").textContent = data.cluster.nodes;
          document.getElementById("pods").textContent = data.cluster.pods;
          document.getElementById("namespaces").textContent = data.cluster.namespaces;
          document.getElementById("updated").textContent = "Updated: " + (data.timestamp || "—");

          // Simple health coloring
          const ok = (data.mode === "kubernetes" || data.mode === "local");
          setDot(ok, !ok);

        } catch (e) {
          err.style.display = "block";
          err.textContent = "Request failed: " + e;
          setDot(false, true);
        }
      }

      load();
      setInterval(load, 5000);
    </script>
  </body>
</html>
"""


# ---- Health check ----
@app.get("/health")
def health():
    return {"status": "ok"}
