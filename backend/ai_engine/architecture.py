"""Deterministic graph structure for Person 1's React Flow component."""

def build(tier):
    if tier is None:
        return {"nodes": [], "connections": []}
    device = {"id": "device", "label": "User Device", "type": "device"}
    if tier == "on_device":
        target = {"id": "inference", "label": "On-device Inference", "type": "device"}
    elif tier == "cloud":
        target = {"id": "cloud", "label": "Cloud Inference", "type": "cloud"}
    else:
        target = {"id": "inference", "label": "Far Edge" if tier == "far_edge" else "Regional Edge", "type": "edge"}
    return {"nodes": [device, target], "connections": [{"source": "device", "target": target["id"]}]}
