import yaml


config_file = "config.yaml"

try:
    with open(config_file, 'r') as stram:
        config = yaml.safe_load(stram)
except yaml.YAMLError as exc:
    print(f"Error loading YAML file: {exc}")

BOT_TOKEN = config["bot_token"]
URL = config["url"]
ADMINS = config["admins"]
