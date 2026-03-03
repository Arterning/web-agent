from urllib.parse import urlparse

parsed = urlparse("http://admin:123@12.22.22.3:5000")

if not parsed.scheme:
    raise Exception(f"代理URL缺少协议: {proxy_url}")

schema = parsed.scheme
proxy_host = parsed.hostname
proxy_port = parsed.port
proxy_username = parsed.username
proxy_password = parsed.password

print(f"代理协议: {schema}")
print(f"代理主机: {proxy_host}")
print(f"代理端口: {proxy_port}")
print(f"代理用户名: {proxy_username}")
print(f"代理密码: {proxy_password}")