import os
from dotenv import load_dotenv

# Path ke .env (parent folder)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')

# Load .env
load_dotenv(env_path)

# Coba print variabel
svc = os.getenv("EE_SERVICE_ACCOUNT")
key = os.getenv("EE_PRIVATE_KEY")
proj = os.getenv("EE_PROJECT")

print("EE_SERVICE_ACCOUNT:", svc)
print("EE_PROJECT:", proj)
print("EE_PRIVATE_KEY ada isinya?", bool(key and key.strip()))
