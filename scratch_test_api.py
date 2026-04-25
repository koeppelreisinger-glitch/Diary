import urllib.request
import urllib.error
import json

BASE_URL = "https://sherri.top/api/v1"

def test():
    # 1. Register
    reg_data = json.dumps({"phone": "13800138999", "password": "testpassword", "username": "testuser_999"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/auth/register", data=reg_data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            print("Reg:", resp.status, resp.read().decode())
    except urllib.error.HTTPError as e:
        print("Reg Err:", e.code, e.read().decode())
        
    # 2. Login
    login_data = json.dumps({"phone": "13800138999", "password": "testpassword"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/auth/login", data=login_data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            token = res["data"]["access_token"]
            print("Login success, token obtained!")
    except urllib.error.HTTPError as e:
        print("Login Err:", e.code, e.read().decode())
        return
        
    # 3. Hit endpoints
    def hit(path):
        r = urllib.request.Request(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(r) as resp:
                print(f"{path}:", resp.status, resp.read().decode()[:100])
        except urllib.error.HTTPError as e:
            print(f"{path} Err:", e.code, e.read().decode())
            
    hit("/daily-records/today")
    hit("/history/events")
    hit("/media/on-this-day")

test()
