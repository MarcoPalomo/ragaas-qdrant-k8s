import requests

print("⚙️ Migrating Qdrant collections schema...")

collections = requests.get("http://localhost:6333/collections").json()["result"]["collections"]
for col in collections:
    name = col["name"]
    print(f" - Checking collection: {name}")
    # Exemple : ajuster un paramètre de distance
    requests.patch(f"http://localhost:6333/collections/{name}", json={
        "optimizer_config": {"default_segment_number": 5}
    })

print("Migration terminée.")