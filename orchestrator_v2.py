from fastapi import FastAPI
import requests
from tabulate import tabulate
import redis
import itertools


#setting up controller db
presence_host = "localhost"
presence_port = 6380
presence_db = redis.StrictRedis(host=presence_host, port=presence_port, decode_responses=True)

#Orchestrator db
controller_host = "localhost"
controller_port = 6381
controller_db = redis.StrictRedis(host=presence_host, port=controller_port, decode_responses=True)

infra_ip = ""
manager_url = f"http:{infra_ip}//:5000"

#setting up data intelligence provide
monitoring_ip = "http://localhost:9001/predict"


latency_constraint = {
    "S1S2":300,
    "S2S3":500,
    "S3S4":500
}

def planifier_placement(latence_data: dict, requirements: dict) -> dict:
    nodes = list(latence_data["uav"].keys())
    uav_latencies = latence_data["uav"]
    node_latencies = latence_data["node_latencies"]

    def get_node_to_node_latency(src, dst):
        if src == dst:
            return float("inf")  # forbid same node
        return node_latencies.get(src, {}).get(dst) or node_latencies.get(dst, {}).get(src) or float("inf")

    valid_placements = []
    all_placements = []

    for s2_node, s3_node in itertools.product(nodes, repeat=2):
        if s2_node == s3_node:
            continue  # skip same-node placements

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



#setting up API
app = FastAPI()


@app.get("/offload")
async def offload_service(latency_data: dict):
    global manager_url, presence_db, monitoring_ip, controller_db, latency_constraint
    
    #define placement plan
    nodes = planifier_placement(latence_data=latency_data, requirements=latency_constraint)
    print(nodes)
    
    #rgistering active nodes 
    controller_db.flushall()
    for item in nodes:
        controller_db.set(nodes[item], item)
    response =  requests.get(manager_url+"/deploy", json=nodes)
    if response.status_code == 200:
        print("Offloading successful")
    else:
        print(f"Error while offloadin services {response.status_code}")

@app.get("/replan")
async def replan(data: dict):
    global latency_constraint, manager_url
    candidates = []
    for item in data:
        candidates.append(item)

    #contact deployer for deployment
    response = requests.get(url=manager_url+"/release", json= {"nodes": candidates})
    if response.status_code == 200:
        print("Service reconfiguration process successful")
    else:
        print("Error while replaning services")

