import os
import requests
import json
from datetime import datetime

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BACKUP_DIR = f"data/backups/{datetime.now().strftime('%Y-%m-%d_%H-%M')}"

os.makedirs(BACKUP_DIR, exist_ok=True)

print("📦 Sauvegarde des collections Qdrant...")
collections = requests.get(f"{QDRANT_URL}/collections").json()["result"]["collections"]

for c in collections:
    name = c["name"]
    print(f" - Export {name}")
    data = requests.get(f"{QDRANT_URL}/collections/{name}/points").json()
    with open(f"{BACKUP_DIR}/{name}.json", "w") as f:
        json.dump(data, f, indent=2)

print("Sauvegarde Qdrant terminée.")
print(f"Sauvegarde terminée : {BACKUP_DIR}")
