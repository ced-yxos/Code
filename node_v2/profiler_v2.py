import redis
import json
import random
import time
import requests
from concurrent.futures import ThreadPoolExecutor

#load time series associated with the nodes
with open("./time_series.json","r") as data:
    historical_data = json.load(data)

#set up connection to db 
presence_host="localhost"
presence_port= 6380
presence_db = redis.StrictRedis(host=presence_host, port=presence_port, decode_responses=True)

#set up connection to db 
controller_host="localhost"
controller_port= 6381
controller_db = redis.StrictRedis(host=controller_host, port=controller_port, decode_responses=True)

#set  up control command
base_command = "kubectl exec -n fire-detection --tty --stdin -c "
clear_argument = "tc qdisc del dev eth0 root"

#controller url
control_ip = "http://194.199.113.18:5000"
predictor_ip = "http://localhost:"


def apply_latency(node: str, latency: int):
    global base_command, clear_argument
    actions = []
    #define latency
    rule = f"tc qdisc add dev eth0 root netem delay {latency}ms"
    command =  base_command + node + " "
    actions.append(command)
    actions.append(rule)
    return(actions)

#Keep track of the latency values for each nodes
indices = {}
for item in historical_data:
    indices[item] = [0, len(historical_data[item]["latencies"])]

#Stores rules list
rules = {}
params_list = []
print(indices)

while True:
    #get active connections
    active_nodes = presence_db.keys("*")
    selected_nodes = controller_db.keys("*")

    print(selected_nodes)
    print(active_nodes)

    #Set up latency config rules
    for node in active_nodes:
        if node == "uav":
            pass
        else:
            index = indices[node][0]
            #update presence server
            presence_db.set(node,historical_data[node]["latencies"][index])
            if node in selected_nodes:
                rules[node] = apply_latency(node, historical_data[node]["latencies"][index])
            indices[node][0] = (indices[node][0]+1)%indices[node][1]
            #save latency for forecasting
            params_list.append({node:historical_data[node]["latencies"][index]})
    
    print(rules)
    #Send latency rules for trafic shaping
    response = requests.get(url=control_ip+"/execute", json=rules)
    time.sleep(5)



