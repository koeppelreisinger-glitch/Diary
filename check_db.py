import asyncio
import os
import subprocess
import socket

def test_port(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((ip, port))
        s.close()
        return True
    except:
        return False

print('=== STEP 1: CONFIGURATION ===')
try:
    from app.core.config import settings
    print(f'POSTGRES_SERVER={settings.POSTGRES_SERVER}')
    print(f'POSTGRES_PORT={settings.POSTGRES_PORT}')
    print(f'POSTGRES_USER={settings.POSTGRES_USER}')
    pwd = settings.POSTGRES_PASSWORD
    print(f'POSTGRES_PASSWORD={"***" if pwd else "Empty"}')
    print(f'POSTGRES_DB={settings.POSTGRES_DB}')
    
    uri = str(settings.SQLALCHEMY_DATABASE_URI)
    if pwd:
        uri = uri.replace(pwd, "***")
    print(f'URI={uri}')
except Exception as e:
    print('Failed to read config:', e)

print('\n=== STEP 2: PG SERVICE STATUS ===')
try:
    output = subprocess.check_output(['powershell', '-Command', 'Get-Service *postgre* | Select-Object Name, Status, DisplayName']).decode('gbk', errors='ignore')
    if not output.strip():
        print("No PostgreSQL service found.")
    else:
        print(output.strip())
except Exception as e:
    print('Failed to check services:', e)

print('\n=== STEP 3: PORT CHECK ===')
try:
    server = settings.POSTGRES_SERVER if 'settings' in locals() else 'localhost'
    port = settings.POSTGRES_PORT if 'settings' in locals() else 5432
    if server == 'localhost':
        server = '127.0.0.1'
    is_open = test_port(server, port)
    print(f"{server}:{port} connectable: {is_open}")
except Exception as e:
    print('Failed to check port:', e)

print('\n=== STEP 4: PSQL CHECK ===')
try:
    output = subprocess.check_output(['psql', '--version']).decode()
    print(output.strip())
except FileNotFoundError:
    print('psql not found in PATH')
except Exception as e:
    print('Failed to run psql:', e)

print('\n=== STEP 5 & 6: DATABASE & TABLE CHECK ===')
async def check_db():
    try:
        if not is_open:
            print("Skipping DB check because port is closed.")
            return
        
        # Connect via SQLAlchemy
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args={"timeout": 5})
        
        async with engine.begin() as conn:
            print(f"Successfully connected to database: {settings.POSTGRES_DB}")
            
            # Check users
            res = await conn.execute(text("SELECT to_regclass('public.users');"))
            val = res.scalar()
            print(f"Table 'users' exists: {bool(val)}")
            
            # Check user_settings
            res = await conn.execute(text("SELECT to_regclass('public.user_settings');"))
            val = res.scalar()
            print(f"Table 'user_settings' exists: {bool(val)}")
            
        await engine.dispose()
    except Exception as e:
        print(f"Database connection or query failed: {e}")

asyncio.run(check_db())
