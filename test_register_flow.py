import urllib.request, json, time, urllib.error

phone = f'137{int(time.time()) % 100000000:08d}'
password = 'Password123!'
base = 'http://127.0.0.1:8000/api/v1'

def post(url, data, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get(url, token):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'}, method='GET')
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read())

print(f'Phone: {phone}')

# 1. 注册
s, r = post(f'{base}/auth/register', {'phone': phone, 'password': password, 'nickname': '联调用户'})
print(f'[注册] HTTP {s}: {r["message"]}')
assert s == 200, f'注册失败: {r}'

# 2. 登录
s, r = post(f'{base}/auth/login', {'phone': phone, 'password': password})
print(f'[登录] HTTP {s}: {r["message"]}')
assert s == 200, f'登录失败: {r}'
token = r['data']['access_token']

# 3. /users/me
s, r = get(f'{base}/users/me', token)
uid = r['data']['id']
uphone = r['data']['phone']
print(f'[用户] HTTP {s}: id={uid[:8]}... phone={uphone}')
assert s == 200

print()
print('✅ 注册→登录→用户信息 全流程正常，后端 API 无问题')
