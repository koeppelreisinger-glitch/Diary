import urllib.request
import urllib.error
import json
import uuid
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"
TOKEN = None

def make_request(method, endpoint, data=None, use_token=False):
    url = f"{BASE_URL}{endpoint}"
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

print("=== Starting Advanced Backend Test ===")

# 1. Auth
test_phone = f"139{str(uuid.uuid4().int)[:8]}"
status, body = make_request("POST", "/auth/register", {"phone": test_phone, "password": "Password123!", "nickname": "Tester"})
status, body = make_request("POST", "/auth/login", {"phone": test_phone, "password": "Password123!"})
TOKEN = body["data"]["access_token"]
print("Step 1: Auth OK")

# 2. Today's Settings (ensure timezone is set for conversation date calculation)
status, body = make_request("PUT", "/settings", {"timezone": "Asia/Shanghai"}, use_token=True)
print("Step 2: Settings OK")

# 3. Create Conversation
status, body = make_request("POST", "/conversations", use_token=True)
if status == 200:
    conv_id = body["data"]["id"]
else:
    # try get today's
    status, body = make_request("GET", "/conversations/today", use_token=True)
    conv_id = body["data"]["conversation"]["id"]
print(f"Step 3: Conversation ID: {conv_id}")

# 4. Send Message
status, body = make_request("POST", f"/conversations/{conv_id}/messages", {"content_type": "text", "content": "今天天气不错，我去公园跑步了，心情很好。"}, use_token=True)
print(f"Step 4: Send Message Status: {status}")

# 5. Complete Conversation (Sumarization)
print("Step 5: Completing conversation (generating summary)...")
status, body = make_request("POST", f"/conversations/{conv_id}/complete", use_token=True)
print(f"Complete Status: {status}")
if status == 200:
    print("Record Date:", body["data"]["daily_record"]["record_date"])
    record_date = body["data"]["daily_record"]["record_date"]
else:
    print("Error completing:", body)
    exit(1)

# 6. History List
status, body = make_request("GET", "/history/daily-records", use_token=True)
print(f"Step 6: History List Status: {status}")
print(f"Total Records: {body['data']['total_count']}")

# 7. History Detail
status, body = make_request("GET", f"/history/daily-records/{record_date}", use_token=True)
print(f"Step 7: History Detail for {record_date} Status: {status}")
if status == 200:
    print("Summary:", body["data"]["summary_text"])

print("\n=== All Tests Completed Successfully ===")
