from fastapi import FastAPI
import subprocess

def get_pod_name(namespace: str, selector: str):

    cmd = f"kubectl get pod -n {namespace} -l app={selector} -o jsonpath='{{.items[0].metadata.name}}'"
    result = subprocess.run(cmd, shell=True,capture_output=True, text=True, check=True)

    return result.stdout.strip()

app = FastAPI()

@app.get("/deploy")
async def deploy_services(nodes: dict):
    clear = subprocess.run("kubectl delete all --all -n fire-detection", shell=True)
    command = "kubectl apply -f "

    #deploying services
    for node in nodes:
        try:
            result = subprocess.run(command+nodes[node]+".yaml -n fire-detection", shell=True, capture_output=True, text=True)
            # print("STDOUT :\n", result.stdout)
            #print("STDERR :\n", result.stderr)
            # print("Code de retour :", result.returncode)
        except Exception as e:
            print(f"Error while offloading service on {nodes}")


@app.get("/execute")
async def execute_rule(actions: dict):
    clear_command = "tc qdisc del dev eth0 root"
    for item in actions:
        pod_name = get_pod_name("fire-detection", item)
        tc_command = actions[item][0]+pod_name+" "
        #clear precedent latency rule
        try:
            result = subprocess.run(tc_command+clear_command, shell=True, capture_output=True, text=True)
            # print("STDOUT :\n", result.stdout)
            # print("STDERR :\n", result.stderr)
            # print("Code de retour :", result.returncode)
        except Exception as e:
            print(f"Error while clearing latency rule")
        #apply new latency rule
        try:
            result = subprocess.run(tc_command+actions[item][1], shell=True, capture_output=True, text=True)
            # print("STDOUT :\n", result.stdout)
            #print("STDERR :\n", result.stderr)
            # print("Code de retour :", result.returncode)
        except Exception as e:
            print(f"Error while clearing latency rule")

@app.get("/release")
async def release_node(data: dict):
    print(data)
    command = "kubectl delete -f "
    for item in data["nodes"]:
        try:
            print(command+item+".yaml")
            result = subprocess.run(command+item+".yaml", shell=True, capture_output=True, text=True)
            #print("STDOUT :\n", result.stdout)
            # print("STDERR :\n", result.stderr)
            # print("Code de retour :", result.returncode)
        except Exception as e:
            print(f"Error while clearing latency rule")