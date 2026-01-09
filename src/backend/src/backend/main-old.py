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

# Local Metrics

metrics_api = client.CustomObjectsApi()


@app.get("/node-usage")
def node_usage():
    node_metrics = metrics_api.list_cluster_custom_object(
        group="metrics.k8s.io",
        version="v1beta1",
        plural="nodes",
    )

    items = []
    for n in node_metrics.get("items", []):
        items.append(
            {
                "node": n["metadata"]["name"],
                "cpu": n["usage"]["cpu"],
                "memory": n["usage"]["memory"],
            }
        )

    return {"items": items}


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
                "services": 0,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    try:
        nodes = core_v1.list_node().items
        pods = core_v1.list_pod_for_all_namespaces().items
        namespaces = core_v1.list_namespace().items
        services = core_v1.list_service_for_all_namespaces().items

        return {
            "mode": mode,
            "cluster": {
                "nodes": len(nodes),
                "pods": len(pods),
                "namespaces": len(namespaces),
                "services": len(services),
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
  <title>Kubernetes Metrics</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <style>
    body {
      margin: 0;
      padding: 32px;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: #0f172a;
      color: #e5e7eb;
    }

    h1 {
      margin-bottom: 4px;
      font-size: 22px;
    }

    .subtitle {
      color: #9ca3af;
      font-size: 13px;
      margin-bottom: 24px;
    }

    .panel {
      background: #111827;
      border: 1px solid #1f2933;
      border-radius: 8px;
      padding: 16px;
      max-width: 520px;
    }

    .row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #1f2933;
    }

    .row:last-child {
      border-bottom: none;
    }

    .label {
      color: #9ca3af;
    }

    .value {
      font-weight: 600;
    }

    .status {
      margin-top: 16px;
      font-size: 13px;
      color: #9ca3af;
    }

    pre {
      margin-top: 24px;
      background: #020617;
      padding: 12px;
      border-radius: 6px;
      font-size: 12px;
      overflow-x: auto;
    }

    .error {
      color: #f87171;
      margin-top: 16px;
      font-size: 13px;
    }
  </style>
</head>

<body>

  <h1>Gin DevOps </h1>
  <h2> Kubernetes Metrics</h2>
  <div class="subtitle">Live data from cluster API</div>

  <div class="panel">
    <div class="row">
      <span class="label">Mode</span>
      <span class="value" id="mode">—</span>
    </div>
    <div class="row">
      <span class="label">Nodes</span>
      <span class="value" id="nodes">—</span>
    </div>
    <div class="row">
      <span class="label">Pods</span>
      <span class="value" id="pods">—</span>
    </div>
    <div class="row">
      <span class="label">Namespaces</span>
      <span class="value" id="namespaces">—</span>
    </div>
    <div class="row">
        <span class="label">Services</span>
        <span class="value" id="allservices">-</span>
    </div>
    </div>
  </div>
  <div class="status" id="updated">Last update: —</div>
  <div class="error" id="error" style="display:none;"></div>

  <pre id="raw">{}</pre>
<h3>Node Resource Usage (Raw)</h3>
<pre id="nodeUsage">loading…</pre>

  <script>
    const API_URL = "/";   // later becomes "/api"

    async function loadMetrics() {
      const errorEl = document.getElementById("error");

      try {
        const res = await fetch(API_URL, { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        if (!data || !data.cluster) {
          throw new Error("Unexpected API response");
        }
		

        document.getElementById("mode").textContent = data.mode;
        document.getElementById("nodes").textContent = data.cluster.nodes;
        document.getElementById("pods").textContent = data.cluster.pods;
        document.getElementById("namespaces").textContent = data.cluster.namespaces;
        document.getElementById("allservices").textContent = data.cluster.services;
        document.getElementById("updated").textContent =
          "Last update: " + (data.timestamp || "unknown");

        document.getElementById("raw").textContent =
          JSON.stringify(data, null, 2);

        errorEl.style.display = "none";

      } catch (err) {
        errorEl.style.display = "block";
        errorEl.textContent = "Error fetching metrics: " + err.message;
      }
    }

    loadMetrics();
    setInterval(loadMetrics, 5000);
  </script>

</body>
</html>

"""


# ---- Health check ----
@app.get("/health")
def health():
    return {"status": "ok"}
