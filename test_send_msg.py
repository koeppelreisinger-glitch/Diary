import json
import urllib.request
from fastapi.testclient import TestClient

# We will just write a python script to hit localhost and dump the responses
import urllib.error

base = "http://127.0.0.1:8000/api/v1"

def req(method, endpoint, token=None, json_data=None):
    url = base + endpoint
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if json_data:
        req.data = json.dumps(json_data).encode('utf-8')
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, str(e)

# 1. login 
import uuid
phone = f"170{str(uuid.uuid4().int)[:8]}"
st, reg_body = req("POST", "/auth/register", json_data={"phone":phone, "password":"Pwd!1234", "nickname":"t1"})
print("Reg err:", reg_body)
st, body = req("POST", "/auth/login", json_data={"phone":phone, "password":"Pwd!1234"})
if "data" not in body or not body["data"]:
    print("Login err:", body)
    exit(1)
token = body["data"]["access_token"]

# 2. create conversation
st, body = req("POST", "/conversations", token=token)
if st != 200:
    if "已存在" in str(body):
        # fetch today's
        st, b2 = req("GET", "/conversations/today", token=token)
        conv_id = b2["data"]["conversation"]["id"]
    else:
        print("Create err:", body)
        exit(1)
else:
    conv_id = body["data"]["id"]

print("Conv ID:", conv_id)

# 3. send message 
st, body = req("POST", f"/conversations/{conv_id}/messages", token=token, json_data={"content_type":"text", "content":"hello"})
print("Send status:", st, body)
