import urllib.request
import urllib.error
import json
import uuid
import time
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"
TOKEN = None

def make_request(method, endpoint, data=None, use_token=False, full_url=None):
    url = full_url if full_url else f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if use_token and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
        
    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = response.read().decode("utf-8")
            return status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except:
            return e.code, body
    except Exception as e:
        return 0, str(e)

print("等待服务器启动...", flush=True)
for i in range(10):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health")
        break
    except:
        time.sleep(1)

print("=== 1. 测试 System (/, /health) ===")
status, body = make_request("GET", "/health", full_url="http://127.0.0.1:8000/health")
print(f"Health Status: {status}")
print(f"Health Response: {body}")

status, body = make_request("GET", "/")
print(f"\nRoot Info Status: {status}")
print(f"Root Info Response: {body}")

print("\n=== 2. 测试 Auth (Register, Login) ===")
# Generate a unique phone number each run to avoid 409 conflict
test_phone = f"186{str(uuid.uuid4().int)[:8]}"
test_password = "SecurePassword123!"

status, body = make_request("POST", "/auth/register", {"phone": test_phone, "password": test_password, "nickname": "HelloUser"})
print(f"\nRegister Status: {status}")
print(f"Register Response: {body}")

status, body = make_request("POST", "/auth/login", {"phone": test_phone, "password": test_password})
print(f"\nLogin Status: {status}")
print(f"Login Response: {body}")

if status == 200 and isinstance(body, dict) and "data" in body:
    TOKEN = body["data"].get("access_token")
    print(f"\n[Info] 获取到 Access Token: {TOKEN[:10]}...")
else:
    print(f"\n[Error] 未获取到 Token，停止后续测试")
    sys.exit(1)

print("\n=== 3. 测试 Users (Get me, Update me) ===")
status, body = make_request("GET", "/users/me", use_token=True)
print(f"\nGet /users/me Status: {status}")
print(f"Get /users/me Response: {body}")

status, body = make_request("PUT", "/users/me", {"nickname": "NewName"}, use_token=True)
print(f"\nUpdate /users/me Status: {status}")
print(f"Update /users/me Response: {body}")

print("\n=== 4. 测试 Settings (Get settings, Update settings) ===")
status, body = make_request("GET", "/settings", use_token=True)
print(f"\nGet /settings Status: {status}")
print(f"Get /settings Response: {body}")

status, body = make_request("PUT", "/settings", {"timezone": "Asia/Shanghai", "input_preference": "text", "reminder_enabled": True, "reminder_time": "22:30"}, use_token=True)
print(f"\nUpdate /settings Status: {status}")
print(f"Update /settings Response: {body}")
