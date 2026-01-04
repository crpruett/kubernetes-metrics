from fastapi import FastAPI
from kubernetes import client, config
from datetime import datetime

app = FastAPI(title="Kubernetes Cluster Metrics")

# Load in-cluster config
config.load_incluster_config()

core_v1 = client.CoreV1Api()


@app.get("/")
def get_cluster_metrics():
    nodes = core_v1.list_node().items
    pods = core_v1.list_pod_for_all_namespaces().items
    namespaces = core_v1.list_namespace().items

    return {
        "cluster": {
            "nodes": len(nodes),
            "pods": len(pods),
            "namespaces": len(namespaces),
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
