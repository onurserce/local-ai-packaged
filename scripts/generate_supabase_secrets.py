import os, time, jwt
from dotenv import dotenv_values
config = dotenv_values(".env")
secret = config["JWT_SECRET"]
now = int(time.time())
exp = now + 10 * 365 * 24 * 60 * 60
def mint(role):
  token = jwt.encode({"role": role, "iss": "supabase", "iat": now, "exp": exp}, secret, algorithm="HS256")
  print(f"{role.upper()}_KEY={token}")
mint("anon")
mint("service_role")