import redis
import json
import random
import time

def select_latency(len:int):
    return random.randint(0,len-1)

def publish(db, data:dict):
    for item in data:
        db.set(item,data[item])      


def generate_random_subset_cav():
    base = [1, 2, 3]
    subset_size = random.randint(1, len(base))
    subset = random.sample(base, subset_size)
    return [f"cav-{i}" for i in sorted(subset)]  

#load time series associated with the nodes
with open("./time_series.json","r") as data:
    historical_data = json.load(data)

#presence server database
presence_port="6380"
presence_host = "localhost"
presence_db = redis.StrictRedis(host=presence_host, port=presence_port, decode_responses=True)

round = 0
old_data = {}

#Simulationg the dynanmic nodes
while True:
    a = input()
    moving_nodes = []
    fixed_nodes = ["fire-lookout-tower-1", "fire-lookout-tower-2", "forest-ranger-1", "forest-ranger-2"]

        #Dynamic nodes joining
    moving_nodes = generate_random_subset_cav()

    #list of connected nodes
    nodes = moving_nodes + fixed_nodes

    print("Current connected nodes: ", nodes)

    #collect list of nodes
    node_list = presence_db.keys("*")
    for item in node_list:
        if item not in nodes:
            presence_db.delete(item)
    
    for item in nodes:
        if item not in node_list:
            presence_db.set(item,"100")
    



