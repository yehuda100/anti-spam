import yaml
import core.utils
import core.mongodb as db
from telegram.ext import filters


config_file = "config.yaml"

try:
    with open(config_file, 'r') as stram:
        config = yaml.safe_load(stram)
except yaml.YAMLError as exc:
    print(f"Error loading YAML file: {exc}")

BOT_TOKEN = config["bot_token"]
URL = config["url"]
ADMINS = config["admins"]


allowed_groups = filters.Chat(core.utils.run_async(db.get_groups))


#by t.me/yehuda100