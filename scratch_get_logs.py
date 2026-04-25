import urllib.request
import json
import sys

TOKEN = "REDACTED"
TEAM_ID = "team_Oaa6g9KqqLsjebA5V4w1qa1H"
PROJECT_ID = "diary"

def get_deployments():
    url = f"https://api.vercel.com/v6/deployments?projectId={PROJECT_ID}&teamId={TEAM_ID}&limit=1"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data["deployments"][0]["uid"]
    except Exception as e:
        print("Error getting deployments:", e)
        sys.exit(1)

def get_logs(dep_id):
    url = f"https://api.vercel.com/v3/events?deploymentId={dep_id}&teamId={TEAM_ID}&limit=20&direction=backward"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            for event in data:
                print(event.get("type"), event.get("payload", {}).get("text", ""))
    except Exception as e:
        print("Error getting logs:", e)

dep_id = get_deployments()
print("Latest Deployment ID:", dep_id)
get_logs(dep_id)
