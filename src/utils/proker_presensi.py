import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

from rich.table import Table

from ui.tui import console, print_log
from utils.credentials import load_credentials
from utils.kkn import KKN
from utils.locations import load_location_config, resolve_location
from utils.logger import get_logger
from utils.simaster import Simaster

log = get_logger("proker_presensi")

RESULT_FILE = Path(os.getenv("REPORT_DIR", "reports")) / "proker-result.json"


def _write_result_json(results: list[dict]):
  try:
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
      json.dump(
        {"generated_at": datetime.now().isoformat(), "type": "proker_presensi", "results": results},
        f,
        indent=2,
        ensure_ascii=False,
      )
    log.info("proker-result.json written to %s (%d users)", RESULT_FILE, len(results))
  except Exception as e:
    log.error("Failed to write proker-result.json: %s", e)


def _print_summary(results: list[dict]):
  table = Table(box=None, title="Proker Presensi Summary")
  table.add_column("User")
  table.add_column("Location")
  table.add_column("Unattended")
  table.add_column("Posted")
  table.add_column("Status")

  for r in results:
    status = r["status"]
    if status == "ok":
      icon = "[green]✓ ok[/]"
    elif status == "skipped":
      icon = "[yellow]– skipped[/]"
    elif status == "no_programs":
      icon = "[yellow]– no_programs[/]"
    elif status == "load_failed":
      icon = "[red]✗ load_failed[/]"
    elif status == "login_failed":
      icon = "[red]✗ login_failed[/]"
    elif status == "no_location":
      icon = "[red]✗ no_location[/]"
    else:
      icon = f"[red]✗ {status}[/]"
    table.add_row(
      r["username"],
      r.get("location", "—"),
      str(r.get("unattended_count", 0)),
      str(r.get("posted_count", 0)),
      icon,
    )

  console.print(table)


async def _process_single_user(
  username: str,
  password: str,
  locations: dict,
  user_locations: dict,
  default_location: str | None,
  dry_run: bool = False,
  throttle: bool = False,
) -> dict:
  """Login as one user, find unattended sub-entries, post attendance. Returns result dict."""
  result = {
    "username": username,
    "status": "ok",
    "unattended_count": 0,
    "posted_count": 0,
    "errors": [],
    "location": "unknown",
  }

  loc = resolve_location(username, locations, user_locations, default_location)
  if loc:
    result["location"] = loc.name
    lat = loc.latitude
    long = loc.longitude
    radius = loc.radius
  else:
    result["status"] = "no_location"
    result["errors"].append("no location configured for this user and no default location")
    log.error("No location configured for %s — skipping proker presensi", username)
    return result

  try:
    simaster = Simaster(username, password)
    session = await simaster.login(verbose=False)
    if not session:
      result["status"] = "login_failed"
      result["errors"].append("login failed")
      log.error("Login failed for %s — skipping proker presensi", username)
      return result

    kkn = KKN(session, simaster, autostart=True)
    if kkn.loader:
      await kkn.loader

    if kkn.load_error:
      result["status"] = "load_failed"
      result["errors"].append(kkn.load_error)
      log.error("Program load failed for %s: %s — skipping proker presensi", username, kkn.load_error)
      await session.aclose()
      return result

    if not kkn.main_program and not kkn.assisted_program:
      result["status"] = "no_programs"
      result["errors"].append("no KKN programs found for this user")
      log.warning("No KKN programs for %s — marking no_programs", username)
      await session.aclose()
      return result

    from actions import _filter_unattended_program

    unattended_main = _filter_unattended_program(kkn.main_program, source="main")
    unattended_assisted = _filter_unattended_program(kkn.assisted_program, source="assisted")
    unattended = [*unattended_main, *unattended_assisted]

    result["unattended_count"] = len(unattended)

    if not unattended:
      log.info("No unattended sub-entries for %s", username)
      result["status"] = "skipped"
      await session.aclose()
      return result

    from utils.common import generate_random_points

    posted = 0
    for item in unattended:
      sub_title = item.get("sub_entry", "unknown")
      url = item.get("url")

      if not url:
        result["errors"].append(f"no attendance_link for: {sub_title}")
        continue

      if dry_run:
        log.info("DRY RUN: would post proker presensi for %s — %s", username, sub_title)
        posted += 1
        continue

      rand_lat, rand_long = generate_random_points(lat, long, radius)
      ok = await kkn.post_logbook_attendance(url, rand_lat, rand_long)
      if ok:
        posted += 1
        log.info("Proker presensi posted for %s — %s", username, sub_title)
      else:
        result["errors"].append(f"failed to post: {sub_title}")

      if throttle:
        delay = random.uniform(2.0, 10.0)
        time.sleep(delay)

    result["posted_count"] = posted
    await session.aclose()
    log.info("Proker presensi for %s: %d/%d posted", username, posted, len(unattended))
    return result

  except Exception as e:
    result["status"] = "error"
    result["errors"].append(str(e))
    log.error("Failed to process %s: %s", username, e, exc_info=True)
    return result


async def handle_proker_presensi(dry_run: bool = False, throttle: bool = True) -> bool:
  """Run proker presensi for all users in SIMASTER_CREDENTIALS (or credentials.json)."""
  creds = load_credentials()
  if not creds:
    print_log("No credentials found — cannot run proker presensi", "ERROR")
    return False

  locations, user_locations, default_location = load_location_config()

  # Validate: warn about users in credentials but not in user_locations
  if user_locations:
    missing = [u for u in creds if u not in user_locations]
    if missing and not default_location:
      log.warning(
        "Users in credentials but not in user_locations (and no default_location): %s — they will be skipped",
        ", ".join(missing),
      )

  # Filter out users with empty passwords
  skipped_empty = []
  valid_creds = {}
  for username, password in creds.items():
    if not password:
      skipped_empty.append(username)
      log.warning("Skipping %s — empty password in credentials", username)
    else:
      valid_creds[username] = password

  if skipped_empty:
    print_log(f"[yellow]Skipped {len(skipped_empty)} users with empty passwords: {', '.join(skipped_empty)}[/]")

  if not valid_creds:
    print_log("No valid credentials found (all passwords empty) — cannot run proker presensi", "ERROR")
    return False

  log.info(
    "Starting proker presensi for %d users (skipped %d with empty passwords)", len(valid_creds), len(skipped_empty)
  )

  # Medium throttle: random startup delay (0-10s)
  if throttle and not dry_run:
    startup_delay = random.uniform(0, 10)
    log.info("Startup throttle: sleeping %.1fs before first proker presensi", startup_delay)
    time.sleep(startup_delay)

  results = []
  usernames = list(valid_creds.keys())
  random.shuffle(usernames)

  for idx, username in enumerate(usernames, 1):
    password = valid_creds[username]
    print(f"Processing proker presensi for {username}...")

    user_result = await _process_single_user(
      username, password, locations, user_locations, default_location, dry_run=dry_run, throttle=throttle
    )
    results.append(user_result)

    # Throttle between users
    if throttle and idx < len(usernames):
      delay = random.uniform(10.0, 30.0)
      log.info("Throttling %.1fs before next user", delay)
      time.sleep(delay)

  _print_summary(results)
  _write_result_json(results)

  ok_count = sum(1 for r in results if r["status"] == "ok")
  skipped_count = sum(1 for r in results if r["status"] == "skipped")
  no_programs_count = sum(1 for r in results if r["status"] == "no_programs")
  load_failed_count = sum(1 for r in results if r["status"] == "load_failed")
  login_failed_count = sum(1 for r in results if r["status"] == "login_failed")
  no_location_count = sum(1 for r in results if r["status"] == "no_location")

  hard_failures = load_failed_count + login_failed_count + no_location_count
  all_ok = hard_failures == 0 and (ok_count + skipped_count + no_programs_count) == len(results)

  if hard_failures:
    level = "ERROR"
    msg = (
      f"Proker presensi done: {ok_count}/{len(results)} OK, "
      f"{load_failed_count} load_failed, {login_failed_count} login_failed, "
      f"{no_location_count} no_location, {no_programs_count} no_programs, "
      f"{skipped_count} skipped"
    )
  elif no_programs_count or skipped_count:
    level = "WARN"
    msg = (
      f"Proker presensi done: {ok_count}/{len(results)} OK, {no_programs_count} no_programs, {skipped_count} skipped"
    )
  else:
    level = "SUCCESS"
    msg = f"Proker presensi done: {ok_count}/{len(results)} users OK"

  print_log(msg, level)
  return all_ok

