from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from kubernetes import client, config
from kubernetes.config import ConfigException
from kubernetes.client.exceptions import ApiException
from datetime import datetime
import uvicorn

from .config import APP_HOST, APP_PORT

app = FastAPI(title="Kubernetes Metrics Dashboard")

core_v1 = None
metrics_api = None
mode = "mock"

# ---- Kubernetes config detection ----
try:
    config.load_incluster_config()
    core_v1 = client.CoreV1Api()
    metrics_api = client.CustomObjectsApi()
    mode = "kubernetes"
except ConfigException:
    try:
        config.load_kube_config()
        core_v1 = client.CoreV1Api()
        metrics_api = client.CustomObjectsApi()
        mode = "local"
    except ConfigException:
        core_v1 = None
        metrics_api = None
        mode = "mock"


# ---- API: Node Resource Usage ----
@app.get("/node-usage")
def node_usage():
    """
    Fetches CPU and memory usage for each node in the cluster.
    Requires metrics-server to be installed in the cluster.
    """
    if metrics_api is None:
        return {
            "mode": mode,
            "error": "Metrics API not available (not connected to cluster)",
            "items": [],
        }

    try:
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

        return {
            "mode": mode,
            "items": items,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except ApiException as e:
        return {
            "mode": mode,
            "error": f"Kubernetes API error: {e.reason}",
            "hint": "Is metrics-server installed? Run: kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
            "items": [],
        }

    except Exception as e:
        return {"mode": mode, "error": f"Unexpected error: {str(e)}", "items": []}


# ---- API: Cluster metrics ----
@app.get("/")
def metrics():
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


# ---- UI: Modern Dashboard ----
@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gin DevOps - Kubernetes Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .metric-card {
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
        }
        .animate-pulse-slow {
            animation: pulse 3s infinite;
        }
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            background-color: #1a202c;
            padding: 2rem;
            border-radius: 10px;
            max-width: 90%;
            max-height: 90%;
            overflow: auto;
            color: white;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
            border: 1px solid #4a5568;
        }
        pre {
            background-color: #2d3748;
            padding: 1rem;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
            animation: pulse 2s infinite;
        }
        .node-card {
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .node-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <header class="gradient-bg shadow-2xl">
        <div class="container mx-auto px-6 py-8">
            <div class="flex items-center justify-between flex-wrap">
                <div class="flex items-center space-x-4">
                    <div class="text-3xl md:text-4xl font-extrabold text-white animate-pulse-slow">
                        <i class="fas fa-server mr-2"></i>
                        Gin DevOps
                    </div>
                    <span class="hidden md:inline-block text-sm text-gray-200">Kubernetes Dashboard</span>
                </div>
                <div class="flex items-center space-x-4">
                    <span id="current-time" class="text-sm md:text-base font-medium text-gray-200"></span>
                    <span id="cluster-info" class="text-lg md:text-xl font-bold text-gray-200">Loading...</span>
                </div>
            </div>
        </div>
    </header>

    <main class="container mx-auto px-6 py-12">
        <div class="text-center mb-12">
            <h1 class="text-4xl md:text-5xl font-bold mb-4">
                Live Kubernetes Metrics
            </h1>
            <p class="text-gray-400 text-lg">
                Real-time cluster monitoring and resource usage
            </p>
        </div>

        <div class="bg-gradient-to-r from-gray-800 to-gray-900 rounded-lg p-8 mb-12 shadow-xl">
            <div class="text-center mb-6">
                <h2 class="text-2xl md:text-3xl font-bold text-white mb-4">Cluster Status</h2>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="text-center">
                    <div class="text-4xl text-blue-400 mb-4">
                        <i class="fas fa-cube"></i>
                    </div>
                    <h3 class="text-xl font-semibold text-blue-300 mb-2">Mode</h3>
                    <p id="status-mode" class="text-gray-300 text-2xl font-bold">—</p>
                </div>
                <div class="text-center">
                    <div class="text-4xl text-green-400 mb-4">
                        <i class="fas fa-clock"></i>
                    </div>
                    <h3 class="text-xl font-semibold text-green-300 mb-2">Last Update</h3>
                    <p id="status-time" class="text-gray-300 text-sm">—</p>
                </div>
                <div class="text-center">
                    <div class="text-4xl text-purple-400 mb-4">
                        <i class="fas fa-heartbeat"></i>
                    </div>
                    <h3 class="text-xl font-semibold text-purple-300 mb-2">Health</h3>
                    <p id="status-health" class="text-gray-300">
                        <span class="status-badge bg-green-500">
                            <span class="status-dot bg-white"></span>
                            Healthy
                        </span>
                    </p>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-12">
            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-blue-400 mb-4">
                    <i class="fas fa-server"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">Nodes</div>
                <div id="nodes-count" class="text-4xl font-extrabold text-blue-300">—</div>
                <div class="text-gray-400">Total</div>
            </div>

            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-purple-400 mb-4">
                    <i class="fas fa-microchip"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">CPU Usage</div>
                <div id="cpu-usage" class="text-4xl font-extrabold text-purple-300">—</div>
                <div class="text-gray-400">Average</div>
            </div>

            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-cyan-400 mb-4">
                    <i class="fas fa-memory"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">Memory Usage</div>
                <div id="memory-usage" class="text-4xl font-extrabold text-cyan-300">—</div>
                <div class="text-gray-400">Average</div>
            </div>

            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-yellow-400 mb-4">
                    <i class="fas fa-cubes"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">Pods Running</div>
                <div id="pods-count" class="text-4xl font-extrabold text-yellow-300">—</div>
                <div class="text-gray-400">Total</div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-green-400 mb-4">
                    <i class="fas fa-layer-group"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">Namespaces</div>
                <div id="namespaces-count" class="text-4xl font-extrabold text-green-300">—</div>
                <div class="text-gray-400">Total</div>
            </div>

            <div class="metric-card bg-gray-800 rounded-lg p-6 shadow-xl flex flex-col items-center text-center">
                <div class="text-4xl text-orange-400 mb-4">
                    <i class="fas fa-network-wired"></i>
                </div>
                <div class="text-xl font-bold text-gray-300 mb-2">Services</div>
                <div id="services-count" class="text-4xl font-extrabold text-orange-300">—</div>
                <div class="text-gray-400">Total</div>
            </div>
        </div>

        <div class="mt-12">
            <h2 class="text-3xl font-bold text-center mb-8">Node Resource Details</h2>
            <div id="node-cards-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div class="text-center text-gray-400">Loading node metrics...</div>
            </div>
        </div>

        <div class="mt-12 text-center space-y-4 md:space-y-0 md:space-x-4 flex flex-col md:flex-row justify-center flex-wrap">
            <button onclick="showNodesModal()" class="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 p-6 rounded-lg text-center transition-all transform hover:scale-105">
                <i class="fas fa-list text-3xl mb-3"></i>
                <div class="font-semibold">Node Details</div>
                <div class="text-xs text-blue-200 mt-1">View All Nodes</div>
            </button>

            <button onclick="showRawDataModal()" class="bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 p-6 rounded-lg text-center transition-all transform hover:scale-105">
                <i class="fas fa-code text-3xl mb-3"></i>
                <div class="font-semibold">Raw Data</div>
                <div class="text-xs text-green-200 mt-1">JSON Response</div>
            </button>

            <button onclick="showInfoModal()" class="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 p-6 rounded-lg text-center transition-all transform hover:scale-105">
                <i class="fas fa-info-circle text-3xl mb-3"></i>
                <div class="font-semibold">About</div>
                <div class="text-xs text-purple-200 mt-1">Dashboard Info</div>
            </button>
        </div>
    </main>

    <footer class="bg-gray-800 border-t border-gray-700 py-8 mt-12">
        <div class="container mx-auto px-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 text-center md:text-left">
                <div>
                    <h3 class="text-lg font-semibold text-white mb-3">Gin DevOps</h3>
                    <div class="space-y-2 text-gray-300 text-sm">
                        <p>Real-time Kubernetes monitoring dashboard</p>
                        <p>Built with FastAPI and Python Kubernetes Client</p>
                    </div>
                </div>
                <div>
                    <h3 class="text-lg font-semibold text-white mb-3">Technologies</h3>
                    <div class="flex flex-wrap gap-2">
                        <span class="bg-blue-600 text-white px-2 py-1 rounded text-xs">Kubernetes</span>
                        <span class="bg-green-600 text-white px-2 py-1 rounded text-xs">FastAPI</span>
                        <span class="bg-purple-600 text-white px-2 py-1 rounded text-xs">Python</span>
                        <span class="bg-yellow-600 text-white px-2 py-1 rounded text-xs">JavaScript</span>
                        <span class="bg-cyan-600 text-white px-2 py-1 rounded text-xs">Tailwind CSS</span>
                    </div>
                </div>
            </div>
            <div class="border-t border-gray-700 mt-8 pt-4 text-center text-gray-400 text-sm">
                <p>&copy; 2025 Gin DevOps | Kubernetes Metrics Dashboard</p>
            </div>
        </div>
    </footer>

    <!-- Nodes Detail Modal -->
    <div id="nodes-modal" class="modal-overlay">
        <div class="modal-content" style="max-width: 1200px;">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-3xl font-bold text-white">
                    <i class="fas fa-server mr-3 text-blue-400"></i>Node Resource Details
                </h2>
                <button onclick="closeNodesModal()" class="text-gray-400 hover:text-white text-2xl">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div id="nodes-modal-content"></div>
            <div class="flex justify-end mt-6">
                <button onclick="closeNodesModal()" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-6 rounded transition-colors">
                    Close
                </button>
            </div>
        </div>
    </div>

    <!-- Raw Data Modal -->
    <div id="raw-modal" class="modal-overlay">
        <div class="modal-content">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-3xl font-bold text-white">
                    <i class="fas fa-code mr-3 text-green-400"></i>Raw API Data
                </h2>
                <button onclick="closeRawDataModal()" class="text-gray-400 hover:text-white text-2xl">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <pre id="raw-data-content">{}</pre>
            <div class="flex justify-end mt-6">
                <button onclick="closeRawDataModal()" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-6 rounded transition-colors">
                    Close
                </button>
            </div>
        </div>
    </div>

    <!-- Info Modal -->
    <div id="info-modal" class="modal-overlay">
        <div class="modal-content">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-3xl font-bold text-white">
                    <i class="fas fa-info-circle mr-3 text-purple-400"></i>About This Dashboard
                </h2>
                <button onclick="closeInfoModal()" class="text-gray-400 hover:text-white text-2xl">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="text-gray-300 space-y-4">
                <p>This dashboard provides real-time monitoring of your Kubernetes cluster.</p>
                <h3 class="text-xl font-bold text-white mt-4">Features:</h3>
                <ul class="list-disc list-inside space-y-2">
                    <li>Live cluster metrics (nodes, pods, namespaces, services)</li>
                    <li>Per-node CPU and memory usage</li>
                    <li>Auto-refresh every 5 seconds</li>
                    <li>Responsive design for all devices</li>
                </ul>
                <h3 class="text-xl font-bold text-white mt-4">Requirements:</h3>
                <ul class="list-disc list-inside space-y-2">
                    <li>Kubernetes cluster access</li>
                    <li>metrics-server installed for resource metrics</li>
                </ul>
                <div class="bg-gray-800 rounded p-4 mt-4">
                    <p class="text-sm text-gray-400">Install metrics-server:</p>
                    <pre class="text-xs mt-2">kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml</pre>
                </div>
            </div>
            <div class="flex justify-end mt-6">
                <button onclick="closeInfoModal()" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-6 rounded transition-colors">
                    Close
                </button>
            </div>
        </div>
    </div>

    <script>
        const API_URL = "/";
        const NODE_USAGE_URL = "/node-usage";
        
        let latestMetricsData = {};
        let latestNodeData = {};

        function updateClock() {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            document.getElementById('current-time').textContent = timeString;
        }

        function parseMemory(memStr) {
            if (!memStr) return 0;
            const match = memStr.match(/^(\\d+)(Ki|Mi|Gi)$/);
            if (!match) return 0;
            const value = parseInt(match[1]);
            const unit = match[2];
            if (unit === 'Ki') return value / 1024 / 1024;
            if (unit === 'Mi') return value / 1024;
            if (unit === 'Gi') return value;
            return 0;
        }

        function parseCPU(cpuStr) {
            if (!cpuStr) return 0;
            if (cpuStr.endsWith('n')) {
                return parseInt(cpuStr) / 1000000;
            }
            if (cpuStr.endsWith('m')) {
                return parseInt(cpuStr);
            }
            return parseFloat(cpuStr) * 1000;
        }

        async function loadMetrics() {
            try {
                const res = await fetch(API_URL, { cache: "no-store" });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                
                const data = await res.json();
                latestMetricsData = data;
                
                if (!data || !data.cluster) throw new Error("Unexpected API response");
                
                document.getElementById('nodes-count').textContent = data.cluster.nodes;
                document.getElementById('pods-count').textContent = data.cluster.pods;
                document.getElementById('namespaces-count').textContent = data.cluster.namespaces;
                document.getElementById('services-count').textContent = data.cluster.services;
                
                document.getElementById('status-mode').textContent = data.mode;
                document.getElementById('status-time').textContent = data.timestamp || 'unknown';
                
                const nodeText = data.cluster.nodes === 1 ? 'Node' : 'Nodes';
                document.getElementById('cluster-info').textContent = `${data.cluster.nodes} ${nodeText}`;
                
            } catch (err) {
                console.error('Error fetching metrics:', err);
                document.getElementById('status-health').innerHTML = '<span class="status-badge bg-red-500"><span class="status-dot bg-white"></span>Error</span>';
            }
        }

        async function loadNodeUsage() {
            try {
                const res = await fetch(NODE_USAGE_URL, { cache: "no-store" });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                
                const data = await res.json();
                latestNodeData = data;
                
                const container = document.getElementById('node-cards-container');
                container.innerHTML = '';
                
                if (data.error) {
                    container.innerHTML = `
                        <div class="col-span-full bg-red-900 bg-opacity-20 border border-red-500 rounded-lg p-6 text-center">
                            <i class="fas fa-exclamation-triangle text-red-400 text-3xl mb-3"></i>
                            <p class="text-red-300">${data.error}</p>
                            ${data.hint ? `<p class="text-red-200 text-sm mt-2">${data.hint}</p>` : ''}
                        </div>
                    `;
                    document.getElementById('cpu-usage').textContent = 'N/A';
                    document.getElementById('memory-usage').textContent = 'N/A';
                    return;
                }
                
                if (data.items && data.items.length > 0) {
                    let totalCPU = 0;
                    let totalMemory = 0;
                    
                    data.items.forEach(node => {
                        const cpuMillis = parseCPU(node.cpu);
                        const memoryGB = parseMemory(node.memory);
                        
                        totalCPU += cpuMillis;
                        totalMemory += memoryGB;
                        
                        const card = document.createElement('div');
                        card.className = 'node-card bg-gray-800 rounded-lg p-6 border-2 border-gray-700 hover:border-blue-500';
                        card.innerHTML = `
                            <div class="flex items-center justify-between mb-4">
                                <div class="flex items-center">
                                    <div class="bg-blue-600 p-3 rounded-lg mr-4">
                                        <i class="fas fa-server text-2xl"></i>
                                    </div>
                                    <div>
                                        <h3 class="text-xl font-bold text-white">${node.node}</h3>
                                    </div>
                                </div>
                                <span class="status-badge bg-green-500">
                                    <span class="status-dot bg-white"></span>
                                    Running
                                </span>
                            </div>
                            <div class="space-y-3">
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-400"><i class="fas fa-microchip mr-2"></i>CPU</span>
                                    <span class="text-purple-300 font-bold">${cpuMillis.toFixed(0)}m</span>
                                </div>
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-400"><i class="fas fa-memory mr-2"></i>Memory</span>
                                    <span class="text-cyan-300 font-bold">${memoryGB.toFixed(2)} GB</span>
                                </div>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                    
                    const avgCPU = data.items.length > 0 ? totalCPU / data.items.length : 0;
                    const avgMemory = data.items.length > 0 ? totalMemory / data.items.length : 0;
                    
                    document.getElementById('cpu-usage').textContent = `${avgCPU.toFixed(0)}m`;
                    document.getElementById('memory-usage').textContent = `${avgMemory.toFixed(1)} GB`;
                } else {
                    container.innerHTML = '<div class="col-span-full text-center text-gray-400">No node metrics available</div>';
                    document.getElementById('cpu-usage').textContent = 'N/A';
                    document.getElementById('memory-usage').textContent = 'N/A';
                }
                
            } catch (err) {
                console.error('Error fetching node usage:', err);
            }
        }

        function showNodesModal() {
            const modal = document.getElementById('nodes-modal');
            const content = document.getElementById('nodes-modal-content');
            
            if (latestNodeData.items && latestNodeData.items.length > 0) {
                content.innerHTML = latestNodeData.items.map(node => {
                    const cpuMillis = parseCPU(node.cpu);
                    const memoryGB = parseMemory(node.memory);
                    return `
                        <div class="bg-gray-800 rounded-lg p-6 mb-4 border border-gray-700">
                            <div class="flex items-center justify-between mb-4">
                                <h3 class="text-2xl font-bold text-white">
                                    <i class="fas fa-server mr-2 text-blue-400"></i>${node.node}
                                </h3>
                                <span class="status-badge bg-green-500">
                                    <span class="status-dot bg-white"></span>
                                    Healthy
                                </span>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div class="bg-gray-900 p-4 rounded">
                                    <p class="text-gray-400 text-sm mb-1">CPU Usage</p>
                                    <p class="text-2xl font-bold text-purple-300">${cpuMillis.toFixed(0)}m</p>
                                    <p class="text-xs text-gray-500 mt-1">Raw: ${node.cpu}</p>
                                </div>
                                <div class="bg-gray-900 p-4 rounded">
                                    <p class="text-gray-400 text-sm mb-1">Memory Usage</p>
                                    <p class="text-2xl font-bold text-cyan-300">${memoryGB.toFixed(2)} GB</p>
                                    <p class="text-xs text-gray-500 mt-1">Raw: ${node.memory}</p>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                content.innerHTML = '<p class="text-gray-400">No node data available</p>';
            }
            
            modal.style.display = 'flex';
        }

        function closeNodesModal() {
            document.getElementById('nodes-modal').style.display = 'none';
        }

        function showRawDataModal() {
            const modal = document.getElementById('raw-modal');
            const content = document.getElementById('raw-data-content');
            
            const combinedData = {
                cluster: latestMetricsData,
                nodes: latestNodeData
            };
            
            content.textContent = JSON.stringify(combinedData, null, 2);
            modal.style.display = 'flex';
        }

        function closeRawDataModal() {
            document.getElementById('raw-modal').style.display = 'none';
        }

        function showInfoModal() {
            document.getElementById('info-modal').style.display = 'flex';
        }

        function closeInfoModal() {
            document.getElementById('info-modal').style.display = 'none';
        }

        window.onclick = function(event) {
            if (event.target.classList.contains('modal-overlay')) {
                event.target.style.display = 'none';
            }
        }

        updateClock();
        setInterval(updateClock, 1000);
        
        loadMetrics();
        loadNodeUsage();
        
        setInterval(() => {
            loadMetrics();
            loadNodeUsage();
        }, 5000);
    </script>
</body>
</html>
"""


# Do it Trigger release please


# ---- Health check ----
@app.get("/health")
def health():
    return {"status": "ok"}


def main():
    "Entry Point for running the app with UV"
    uvicorn.run("backend.main:app", host=APP_HOST, port=APP_PORT, reload=True)


if __name__ == "__main__":
    main()
