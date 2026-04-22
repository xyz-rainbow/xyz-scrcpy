import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../config/config.json')

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f: return json.load(f)
    return {"default_audio": "output", "autostart": false, "resolution": "1080p"}

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f: json.dump(cfg, f, indent=2)
