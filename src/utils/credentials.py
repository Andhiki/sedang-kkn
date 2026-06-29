import json
import os
from pathlib import Path

from utils.logger import get_logger

log = get_logger("credentials")

CREDENTIALS_FILE = Path(os.getenv("CREDENTIALS_FILE", "credentials.json"))


def load_credentials() -> dict[str, str]:
  """Load SIMASTER credentials {username: password} from env or file.

  Priority:
    1. SIMASTER_CREDENTIALS env var (JSON string — used in CI/CD)
    2. credentials.json file (local dev)
  """
  raw = os.getenv("SIMASTER_CREDENTIALS")
  if raw:
    try:
      creds = json.loads(raw)
      if not isinstance(creds, dict):
        log.error("SIMASTER_CREDENTIALS must be a JSON object {username: password}")
        return {}
      return creds
    except json.JSONDecodeError as e:
      log.error("SIMASTER_CREDENTIALS is not valid JSON: %s", e)
      return {}

  if CREDENTIALS_FILE.exists():
    try:
      with open(CREDENTIALS_FILE, encoding="utf-8") as f:
        creds = json.load(f)
      if not isinstance(creds, dict):
        log.error("credentials.json must be a JSON object {username: password}")
        return {}
      return creds
    except (json.JSONDecodeError, OSError) as e:
      log.error("Failed to read credentials.json: %s", e)
      return {}

  log.error("No credentials found — set SIMASTER_CREDENTIALS env or create credentials.json")
  return {}