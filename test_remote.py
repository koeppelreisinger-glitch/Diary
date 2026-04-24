import urllib.request, urllib.error, json, time, ssl

BASE = 'https://www.shuhan.xyz'
ctx = ssl.create_default_context()

def req(method, path, data=None, token=None):
    url = f'{BASE}{path}'
    body = json.dumps(data).encode('utf-8') if data else None
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20, context=ctx) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        return e.code, raw
    except Exception as ex:
        return 0, str(ex)

phone = f'135{int(time.time()) % 100000000:08d}'
pwd = 'Password123!'
print(f'Target: {BASE}')
print(f'Phone:  {phone}')
print('='*60)

# 1. Health check
print('\n[1] GET /health')
s, r = req('GET', '/health')
print(f'HTTP {s}')
print(r[:300])

# 2. Register
print('\n[2] POST /api/v1/auth/register')
s, r = req('POST', '/api/v1/auth/register', {'phone': phone, 'password': pwd, 'nickname': 'TestUser'})
print(f'HTTP {s}')
print(r[:500])

# 3. Login (only if register success)
token = None
if s == 200:
    print('\n[3] POST /api/v1/auth/login')
    s2, r2 = req('POST', '/api/v1/auth/login', {'phone': phone, 'password': pwd})
    print(f'HTTP {s2}')
    print(r2[:300])
    if s2 == 200:
        token = json.loads(r2)['data']['access_token']

        print('\n[4] GET /api/v1/users/me')
        s3, r3 = req('GET', '/api/v1/users/me', token=token)
        print(f'HTTP {s3}')
        print(r3[:300])
else:
    print('\n=> 注册失败，跳过登录测试')
    print('尝试查看 OpenAPI 文档...')
    s4, r4 = req('GET', '/api/v1/openapi.json')
    print(f'GET /api/v1/openapi.json -> HTTP {s4}')
    print(r4[:200])
