import yaml, json
from datetime import datetime

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
