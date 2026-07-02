import random
import re
from typing import Literal

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.panel import Panel

console = Console()
try:
  prompt_session = PromptSession()
except Exception:
  prompt_session = None

type Level = Literal["SUCCESS", "ERROR", "WARN"]

PREFIX = {
  "SUCCESS": "[bold green] SUCCESS[/][#89dceb]:[/] ",
  "ERROR": "[bold red] ERROR[/][#89dceb]:[/] ",
  "WARN": "[bold yellow] WARNING[/][#89dceb]:[/] ",
}


def print_log(message: str, level: Level = "WARN"):
  prefix = PREFIX[level]
  console.print(f"{prefix}{message}")


def _parse_duration_hours(duration_str: str) -> float:
  if not duration_str or duration_str == "N/A":
    return 0.0
  text = duration_str.lower().strip()
  match = re.search(r"[\d.]+", text)
  if not match:
    return 0.0
  val = float(match.group())
  if "menit" in text:
    return val / 60.0
  return val


def _format_hours(total: float) -> str:
  hours = int(total)
  minutes = int((total - hours) * 60)
  if hours and minutes:
    return f"{hours} jam {minutes} menit"
  if hours:
    return f"{hours} jam"
  return f"{minutes} menit"


def _sum_program_hours(data) -> float:
  total = 0.0
  if not data:
    return total
  for value in data.values():
    entries = value if isinstance(value, list) else value.get("entries", [])
    for entry in entries:
      for sub in entry.get("sub_entries", []):
        total += _parse_duration_hours(sub.get("duration", "N/A"))
  return total


def print_hours_summary(main_program: dict, assisted_program: dict | None):
  main_hours = _sum_program_hours(main_program or {})
  assisted_hours = _sum_program_hours(assisted_program or {})
  console.print(
    Panel(
      f"[#89dceb]Proker Utama:[/] {_format_hours(main_hours)}    "
      f"[#89dceb]Program Bantu:[/] {_format_hours(assisted_hours)}",
      title="[bold #89dceb]Jam Tercatat[/]",
      expand=False,
    )
  )


def print_title():
  title = [
    "[#99FF99]▄▄▄    ▄▄▄          ████                         ▄▄▄  ▄▄▄ ▄▄▄  ▄▄▄ ▄▄▄  ▄▄▄[/]",
    "[#99FFB2]███▄  ▄███  ██████▄  ███   ██████▄ ▄███████      ███  ███ ███  ███ ███▄ ███[/]",
    "[#99FFCC]██████████ ▄▄▄▄▄███  ███  ▄▄▄▄▄███ ▀██▄▄▀▀▀ ▄▄▄▄ ████▄██▀ ████▄██▀ ████▄███[/]",
    "[#99FFE5]███ ▀▀ ███ ███▀▀███  ███  ███▀▀███   ▀▀███▄ ▀▀▀▀ ███▀███▄ ███▀███▄ ███▀████[/]",
    "[#99FFFF]███    ███ ▀███████ █████ ▀███████ ███████▀      ███  ███ ███  ███ ███ ▀███[/]",
  ]

  splash_text = [
    "Because life is too short for manual logbook",
    "I don't have enough time to deal with this sh*t",
    "Imagine doing this manually through the web, lmao",
    "Speedrunning KKN Administrative Tasks (Any%)",
    "Constructing payload... Target locked... Attendance posted",
    "Powered by caffeine and hatred for legacy code",
    "Who's in the right mind sending back a 100kb HTML file??",
    "Does anyone actually read these logbooks? asking for a script.",
    "Generating 'productive' activity descriptions...",
    "Fake it 'til you automate it.",
  ]

  random_quotes = f"\n{random.choice(splash_text):^75}\n"
  console.print(("\n".join(title)))
  print(random_quotes)


def print_choice():
  options = [
    "Post Daily Attendance",
    "Show Programs",
    "Manage Logbook Entry (My Program)",
    "Manage Sub-Entry (My Program)",
    "Post Attendance for Unattended Entries",
    "Generate Activity Timeline",
    "Change Account",
    "Refresh",
    "Exit",
  ]

  opt_len = len(str(len(options)))
  for i, opt in enumerate(options, 1):
    fmt_opt = f"[#89dceb][[#fab387]{i:0{opt_len}}[/]][/] {opt}"
    console.print(fmt_opt)

  print()
