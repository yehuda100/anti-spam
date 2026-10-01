import os
import subprocess
import sys
from pathlib import Path

import pytest

from config import ConfigError, load_config


ROOT = Path(__file__).resolve().parents[1]


def _run(code, env):
    try:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"import blocked, possibly waiting on MongoDB:\n{exc}")


def test_import_does_not_connect_to_mongodb(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "bot_token: '123:abc'\nurl: 'https://example.invalid/'\nadmins: [1]\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["CONFIG_FILE"] = str(config_path)
    result = _run(
        "import core.mongodb as db\n"
        "import config\n"
        "import core.callbacks\n"
        "import main\n"
        "assert db._client is None\n"
        "print('imported')\n",
        env,
    )
    assert result.returncode == 0, result.stderr


def test_missing_config_import_raises_config_error(tmp_path):
    env = os.environ.copy()
    env["CONFIG_FILE"] = str(tmp_path / "missing.yaml")
    result = _run("import config\n", env)
    assert result.returncode != 0
    assert "ConfigError" in result.stderr
    assert "Missing configuration file" in result.stderr
    assert "FileNotFoundError" not in result.stderr
    assert "NameError" not in result.stderr


def test_load_config_rejects_empty_and_invalid_yaml(tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML mapping"):
        load_config(str(empty))

    broken = tmp_path / "broken.yaml"
    broken.write_text(":\n  - [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Error loading YAML"):
        load_config(str(broken))

    missing_key = tmp_path / "partial.yaml"
    missing_key.write_text("bot_token: t\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="url"):
        load_config(str(missing_key))


def test_log_chat_id_is_optional():
    import config

    assert config.LOG_CHAT_ID is None
