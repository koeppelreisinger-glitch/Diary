"""
精确模拟 test-console.js 的 registerUser + loginUser 流程
验证修 bug 后前端注册登录是否正常
"""
import urllib.request
import urllib.error
import json
import random

BASE = "http://127.0.0.1:8000/api/v1"


def do_request(path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def sep(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print("="*50)


phone = "18" + str(random.randint(100000000, 999999999))
pw = "Password123!"
print(f"Test phone: {phone}")

# ─────────────────────────────────────────────────
# 模拟 registerUser（修复后：注册 + 自动登录）
# ─────────────────────────────────────────────────
sep("registerUser flow")

# Step 1: /auth/register
s, r = do_request("/auth/register", {"phone": phone, "password": pw, "nickname": "联调用户"})
print(f"[1] Register  HTTP {s} | code={r['code']} | phone={r['data']['phone']}")
assert s == 200 and r["code"] == 20000, f"Register failed: {r}"

# Step 2: auto-login (新增代码)
s, r = do_request("/auth/login", {"phone": phone, "password": pw})
print(f"[2] AutoLogin HTTP {s} | code={r['code']} | token_ok={len(r['data']['access_token'])>20}")
assert s == 200 and r["code"] == 20000, f"Auto-login failed: {r}"
token = r["data"]["access_token"]

# Step 3: getCurrentUserProfile(silent) → /users/me
s, r = do_request("/users/me", token=token)
print(f"[3] /users/me HTTP {s} | code={r['code']} | user={r['data']['id'][:8]}... | phone={r['data']['phone']}")
assert s == 200 and r["code"] == 20000, f"GetMe failed: {r}"

print(">>> registerUser flow PASSED ✓")

# ─────────────────────────────────────────────────
# 模拟 logoutConsole + loginUser（修复后：errors silenced）
# ─────────────────────────────────────────────────
sep("loginUser flow (after logout)")

# Step 1: /auth/login
s, r = do_request("/auth/login", {"phone": phone, "password": pw})
print(f"[1] Login     HTTP {s} | code={r['code']}")
assert s == 200 and r["code"] == 20000, f"Login failed: {r}"
token2 = r["data"]["access_token"]

# Step 2: getCurrentUserProfile(silent) → /users/me
s, r = do_request("/users/me", token=token2)
print(f"[2] /users/me HTTP {s} | nickname={r['data']['nickname']}")
assert s == 200 and r["code"] == 20000, f"GetMe failed: {r}"

print(">>> loginUser flow PASSED ✓")

# ─────────────────────────────────────────────────
# 模拟 409 重复注册（应该显示错误，不崩溃）
# ─────────────────────────────────────────────────
sep("Duplicate register (409 expected)")
s, r = do_request("/auth/register", {"phone": phone, "password": pw, "nickname": "重复用户"})
print(f"[1] Dup-Reg   HTTP {s} | code={r['code']} | msg={r['message']}")
assert s == 409, f"Expected 409, got {s}"
print(">>> 409 handled correctly ✓")

print("\n" + "="*50)
print("  ALL TESTS PASSED — 注册登录流程已修复正常 ✓")
print("="*50)
