import redis
import requests
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import itertools

with open("./nodes/time_series.json", "r") as file:
    historical_data = json.load(file)

controller_host = "localhost"
controller_port = 6381
controller_db = redis.StrictRedis(host=controller_host, port=controller_port, decode_responses=True)

presence_port = 6380
presence_host = "localhost"
presence_db = redis.StrictRedis(host=presence_host, port=presence_port, decode_responses=True)

predictor_ip = "http://localhost:"
controller_ip = "http://localhost:5000/offload"

latency_constraint = {
    "S1S2": 300,
    "S2S3": 500,
    "S3S4": 500
}

def log_event(event_type: str, payload: dict):
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "event": event_type,
        **payload
    }
    with open("execution_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

def missing_elements(reference_list, target_list):
    return [elem for elem in reference_list if elem not in target_list]

def build_latency_data(forecasted_latencies: dict) -> dict:
    nodes = [n for n in forecasted_latencies if n != "uav"]
    uav_latencies = {
        node: forecasted_latencies["uav"] + forecasted_latencies[node]
        for node in nodes
    }
    node_latencies = {}
    for src, dst in itertools.permutations(nodes, 2):
        node_latencies.setdefault(src, {})[dst] = forecasted_latencies[src] + forecasted_latencies[dst]
    return {"uav": uav_latencies, "node_latencies": node_latencies}

def gather_data(db):
    keys = db.keys("*")
    return {key: db.get(key) for key in keys}

def fetch(params):
    global historical_data, predictor_ip
    node = list(params.keys())[0]
    if node != "uav":
        response = requests.get(url=predictor_ip + str(historical_data[node]["port"]) + "/predict", params={"input_data": params[node]})
        latency_prediction = response.json()["prediction"].strip("[]").split()
        return {node: float(latency_prediction[0])}

def check_latency_constraints(placement: dict, forecasted_latencies: dict, latency_constraint: dict) -> dict:
    node_S2 = next(node for node, svc in placement.items() if svc == "S2")
    node_S3 = next(node for node, svc in placement.items() if svc == "S3")
    node_S1 = node_S4 = "uav"

    lat_S1S2 = forecasted_latencies[node_S1] + forecasted_latencies[node_S2]
    lat_S2S3 = forecasted_latencies[node_S2] + forecasted_latencies[node_S3]
    lat_S3S4 = forecasted_latencies[node_S3] + forecasted_latencies[node_S4]

    report = {
        "respected": True,
        "details": {
            "S1→S2": {"latency": lat_S1S2, "constraint": latency_constraint["S1S2"], "ok": lat_S1S2 <= latency_constraint["S1S2"]},
            "S2→S3": {"latency": lat_S2S3, "constraint": latency_constraint["S2S3"], "ok": lat_S2S3 <= latency_constraint["S2S3"]},
            "S3→S4": {"latency": lat_S3S4, "constraint": latency_constraint["S3S4"], "ok": lat_S3S4 <= latency_constraint["S3S4"]}
        }
    }
    if not all(item["ok"] for item in report["details"].values()):
        report["respected"] = False
    return report

try:
    while True:
        params_list = []
        merged_results = {}
        active_nodes = controller_db.keys("*")
        present_nodes = presence_db.keys("*")

        result = all(elem in present_nodes for elem in active_nodes)

        if result:
            for node in active_nodes:
                params_list.append({node: presence_db.get(node)})

            with ThreadPoolExecutor(max_workers=7) as executor:
                results = list(executor.map(fetch, params_list))

            for item in results:
                merged_results.update(item)
            merged_results["uav"] = 15

            placement = gather_data(controller_db)

            print(merged_results)
            print("Current placement: ", placement)

            try:
                node_S2 = next(node for node, svc in placement.items() if svc == "S2")
                node_S3 = next(node for node, svc in placement.items() if svc == "S3")

                predicted_s2 = merged_results.get(node_S2, float("inf"))
                predicted_s3 = merged_results.get(node_S3, float("inf"))
                predicted_execution_time = 2 * 15 + predicted_s2 + predicted_s3
                print("Predicted execution time: ", predicted_execution_time)

                log_event("predicted_execution", {
                    "S2": node_S2,
                    "S3": node_S3,
                    "latency_S2": predicted_s2,
                    "latency_S3": predicted_s3,
                    "execution_time_ms": predicted_execution_time
                })

                actual_s2 = float(presence_db.get(node_S2))
                actual_s3 = float(presence_db.get(node_S3))
                actual_execution_time = 2 * 15 + actual_s2 + actual_s3
                print("Actual execution time: ", actual_execution_time)

                log_event("actual_execution", {
                    "S2": node_S2,
                    "S3": node_S3,
                    "latency_S2": actual_s2,
                    "latency_S3": actual_s3,
                    "actual_execution_time_ms": actual_execution_time
                })

                status = check_latency_constraints(placement, merged_results, latency_constraint)
                if not status["respected"]:
                    adapt_start = time.time()
                    log_event("adaptation_start", {"reason": "latency_violation"})

                    for node in present_nodes:
                        if node != 'uav':
                            params_list.append({node: presence_db.get(node)})

                    with ThreadPoolExecutor(max_workers=7) as executor:
                        results = list(executor.map(fetch, params_list))

                    for item in results:
                        merged_results.update(item)
                    merged_results["uav"] = 15

                    placement = gather_data(controller_db)
                    latency_data = build_latency_data(forecasted_latencies=merged_results)
                    requests.get(url=controller_ip, json=latency_data)

                    adapt_end = time.time()
                    log_event("adaptation_end", {"duration_sec": adapt_end - adapt_start})

            except Exception as e:
                print("Error during placement check:", e)

        else:
            adapt_start = time.time()
            missing_node = missing_elements(present_nodes, active_nodes)
            log_event("adaptation_start", {"reason": f"Missing node(s): {missing_node}"})
            presence_list = gather_data(presence_db)
            for item in presence_list:
                presence_list[item] = float(presence_list[item])
            merged_results = presence_list
            merged_results["uav"] = 15
            latency_data = build_latency_data(forecasted_latencies=merged_results)
            requests.get(url=controller_ip, json=latency_data)
            adapt_end = time.time()
            log_event("adaptation_end", {"reason": "Missing node recovery", "duration_sec": adapt_end - adapt_start})

        time.sleep(5)
except KeyboardInterrupt:
    print(" Interrupted by user. Saving state and exiting cleanly.")
    log_event("shutdown", {"reason": "Manual interrupt (Ctrl+C)"})
    print("✔️ System shut down successfully at", datetime.utcnow().isoformat())


