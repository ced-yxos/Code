import json
import itertools
import requests
import redis


latency_constraint = {
    "S1S2":300,
    "S2S3":500,
    "S3S4":500
}

# Redis connection parameters
presence_port = 6380
presence_host = "localhost"
presence_db = redis.StrictRedis(host=presence_host, port=presence_port, decode_responses=True)

def extract_first_latencies(json_file_path: str) -> dict:
    with open(json_file_path, "r") as f:
        data = json.load(f)

    first_latencies = {}

    for node, infos in data.items():
        latencies = infos.get("latencies", [])
        first_value = latencies[0] if latencies else None
        first_latencies[node] = first_value

    return first_latencies

def build_latency_data(forecasted_latencies: dict) -> dict:
    # Separate the nodes (exclude the UAV)
    nodes = [n for n in forecasted_latencies if n != "uav"]

    # UAV ↔ node latency = sum of interface latencies
    uav_latencies = {
        node: forecasted_latencies["uav"] + forecasted_latencies[node]
        for node in nodes
    }

    # Node ↔ node latency = sum of their interface latencies
    node_latencies = {}
    for src, dst in itertools.permutations(nodes, 2):
        node_latencies.setdefault(src, {})[dst] = forecasted_latencies[src] + forecasted_latencies[dst]

    # Final structure
    latency_data = {
        "uav": uav_latencies,
        "node_latencies": node_latencies
    }

    return latency_data

def planifier_placement(latence_data: dict, requirements: dict) -> dict:
    nodes = list(latence_data["uav"].keys())
    uav_latencies = latence_data["uav"]
    node_latencies = latence_data["node_latencies"]

    def get_node_to_node_latency(src, dst):
        if src == dst:
            return 0
        return node_latencies.get(src, {}).get(dst) or node_latencies.get(dst, {}).get(src) or float("inf")

    valid_placements = []
    all_placements = []

    for s2_node, s3_node in itertools.product(nodes, repeat=2):
        lat_S1S2 = uav_latencies.get(s2_node, float("inf"))
        lat_S2S3 = get_node_to_node_latency(s2_node, s3_node)
        lat_S3S4 = uav_latencies.get(s3_node, float("inf"))
        total_latency = lat_S1S2 + lat_S2S3 + lat_S3S4

        placement = {
            "S2": s2_node,
            "S3": s3_node,
            "latencies": {
                "S1→S2": lat_S1S2,
                "S2→S3": lat_S2S3,
                "S3→S4": lat_S3S4
            },
            "total_latency": total_latency
        }

        all_placements.append(placement)

        if (
            lat_S1S2 <= requirements["S1S2"] and
            lat_S2S3 <= requirements["S2S3"] and
            lat_S3S4 <= requirements["S3S4"]
        ):
            valid_placements.append(placement)

    valid_placements.sort(key=lambda x: x["total_latency"])
    all_placements.sort(key=lambda x: x["total_latency"])

    best = valid_placements[0] if valid_placements else all_placements[0]

    return {
        "S2": best["S2"],
        "S3": best["S3"]
    }


# Exemple d'utilisation :
#Initialiser les latences des noeuds
result = extract_first_latencies("time_series.json")
result["uav"]= 15

for item in result:
    presence_db.set(item, result[item])
    
data = build_latency_data(result)
a = input()
print(data)

response = requests.get(url="http://localhost:5000/offload", json=data)
print(response.status_code)
# print(data)

placement = planifier_placement(data, latency_constraint)
print(placement)




