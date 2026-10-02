import os

import yaml
from telegram.ext import filters


CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.yaml")
_REQUIRED = ("bot_token", "url", "admins")


class ConfigError(Exception):
    """Raised when the bot configuration file is missing or invalid."""


def load_config(path=None):
    path = path or os.environ.get("CONFIG_FILE", "config.yaml")
    if not os.path.exists(path):
        raise ConfigError(
            f"Missing configuration file {path}. Create it locally (do not commit it) "
            "with keys 'bot_token', 'url', and 'admins' (Telegram user ids). "
            "Optional 'log_chat_id' receives one plain-text line per ban."
        )
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Error loading YAML file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path} must be a YAML mapping with bot_token, url, and admins."
        )
    missing = [key for key in _REQUIRED if data.get(key) in (None, "")]
    if missing:
        raise ConfigError(
            f"{path} is missing required setting(s): {', '.join(missing)}."
        )
    return data


_config = load_config(CONFIG_FILE)

BOT_TOKEN = _config["bot_token"]
URL = _config["url"]
ADMINS = _config["admins"]
# Optional. When unset, bans are not posted to a log chat.
LOG_CHAT_ID = _config.get("log_chat_id") or None

# Chat ids are loaded when the application starts. Importing this module must
# not open a MongoDB connection.
allowed_groups = filters.Chat()


#by t.me/yehuda100
