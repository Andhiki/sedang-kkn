import os
import re
from datetime import datetime

from rich import box
from rich.align import Align
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

import utils.generative as gen
from datatypes import EntryData, LogEntryPayload, RPPData, SubEntryData
from ui.tables import print_program_entries, print_program_sub_entries
from ui.tui import console, print_log
from utils.common import generate_random_points


def parse_selection(input_str: str) -> list[int]:
  selected = set()
  tokens = input_str.split()

  for token in tokens:
    try:
      if "-" in token:
        start_str, end_str = token.split("-", 1)
        start, end = int(start_str), int(end_str)

        lower, upper = min(start, end), max(start, end)
        selected.update(range(lower, upper + 1))
      else:
        selected.add(int(token))
    except ValueError:
      print_log(f"Token: '{token}' is not a number or a hyphen")
      continue

  return sorted(list(selected))


def get_entry_details_from_user(
  data: RPPData, edit_mode: bool = False, existing: dict | None = None
) -> LogEntryPayload | None:
  console.print(f"\nCurrent entries for [bold blue]{data['title']}")
  print_program_entries(data)

  default_title = existing.get("title", "") if (edit_mode and existing) else ""
  default_date = (
    existing.get("date", datetime.now().strftime("%Y-%m-%d"))
    if (edit_mode and existing)
    else datetime.now().strftime("%Y-%m-%d")
  )

  prompt_text = "Enter the title for the logbook entry (Kegiatan)"
  entry_title = Prompt.ask(prompt_text, default=default_title)
  activity_datetime = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)

  default_lat = os.getenv("KKN_LOCATION_LATITUDE", "0.0")
  default_long = os.getenv("KKN_LOCATION_LONGITUDE", "0.0")

  latitude = float(default_lat)
  longitude = float(default_long)
  if edit_mode and existing and (loc := existing.get("location")):
    parts = loc.split(",")
    if len(parts) == 2:
      try:
        latitude = float(parts[0].strip())
        longitude = float(parts[1].strip())
      except ValueError:
        pass

  console.print(f"[blue]Current/default point: [yellow]([#fab387]{latitude}[#89dceb],[/] {longitude}[/])[/]")
  use_coord = Confirm.ask("Use this location?", default=True)

  if not use_coord:
    try:
      latitude = float(input("Enter new latitude: "))
      longitude = float(input("Enter new longitude: "))
    except ValueError:
      print_log("Invalid input for location. Using defaults...", "ERROR")
      latitude = float(default_lat)
      longitude = float(default_long)

  form_data = Table(box=box.ROUNDED, title="Summary")
  form_data.add_column(Align.center("Field"), style="bold #89dceb")
  form_data.add_column(Align.center("Content"), overflow="fold")

  form_data.add_row("Title", entry_title)
  form_data.add_row("Date", activity_datetime)

  location = Table(box=box.ROUNDED, show_header=False)
  location.add_row("[bold]Latitude", f"[#fab387]{latitude}")
  location.add_row("[bold]Longitude", f"[#fab387]{longitude}")

  form_data.add_row("Location", location)

  console.print(form_data)
  confirm_text = "Do you want to update this entry?" if edit_mode else "Do you want to add this entry?"
  confirm = Confirm.ask(confirm_text, default=True)

  if not confirm:
    console.print("Operation cancelled.")
    return

  random_lat, random_long = generate_random_points(latitude, longitude, 15)

  return {"title": entry_title, "date": activity_datetime, "longitude": longitude, "latitude": latitude}


def _parse_duration(value: str) -> str:
  match = re.search(r"\d+", value)
  return match.group(0) if match else "60"


def _parse_datetime(value: str) -> tuple[str, str]:
  """Return (date, time) from strings like '2025-07-02 09:00'."""
  now = datetime.now()
  default_date = now.strftime("%Y-%m-%d")
  default_time = now.strftime("%H:%M")
  parts = value.strip().split()
  if len(parts) >= 2:
    return parts[0], parts[1]
  if len(parts) == 1:
    if ":" in parts[0]:
      return default_date, parts[0]
    return parts[0], default_time
  return default_date, default_time


def get_sub_entry_details_from_user(
  data: RPPData,
  edit_mode: bool = False,
  entry: EntryData | None = None,
  existing_sub: SubEntryData | None = None,
):
  program_title = data["title"]

  if entry:
    sub_entry = entry
    console.print(f"\nSub-entry under [bold blue]{sub_entry['title']}")
    print_program_sub_entries(sub_entry)
  else:
    console.print(f"\nCurrent entries for [bold blue]{data['title']}")
    print_program_entries(data)

    length = len(data["entries"])
    choice = int(
      Prompt.ask(
        f"Enter your choice [#89dceb]([#fab387]1[#89dceb]-[/]{length}[/])[/]",
        choices=[str(i + 1) for i in range(length)],
      )
    )

    sub_entry = data["entries"][choice - 1]
    console.print(f"\nCurrent sub-entries for [bold blue]{sub_entry['title']}")
    print_program_sub_entries(sub_entry)

  defaults = {}
  if edit_mode and existing_sub:
    existing_date, existing_time = _parse_datetime(existing_sub.get("date", ""))
    defaults = {
      "title": existing_sub.get("title", ""),
      "duration": _parse_duration(existing_sub.get("duration", "60")),
      "date": existing_date,
      "time": existing_time,
      "target": "-",
      "audience": "0",
      "budget": "0",
      "description": "",
      "result": "",
    }

  sub_entry_title = Prompt.ask(
    "Enter the title for the logbook sub-entry (Kegiatan)", default=defaults.get("title", "")
  )
  duration = Prompt.ask("Enter the duration in minutes", default=defaults.get("duration", "60"))

  activity_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
  target = defaults.get("target", "-")
  audience = defaults.get("audience", "0")
  budget = defaults.get("budget", "0")

  fill_details = Confirm.ask(
    "Do you want to fill in additional details (date, time, participants, etc.)?", default=False
  )

  if fill_details or edit_mode:
    default_date = defaults.get("date", datetime.now().strftime("%Y-%m-%d"))
    default_time = defaults.get("time", datetime.now().strftime("%H:%M"))

    date_input = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)
    time_input = Prompt.ask("Enter time (HH:MM)", default=default_time)

    activity_datetime = f"{date_input} {time_input}"
    target = Prompt.ask("Enter target audience (sasaran)", default=target)
    audience = Prompt.ask("Enter number of participants (jumlah peserta)", default=audience)
    budget = Prompt.ask("Enter amount of funds (jumlah dana)", default=budget)

  description = defaults.get("description", "")
  result = defaults.get("result", "Kegiatan terlaksana dengan baik.")
  jok = int(int(audience) * (int(duration) / 60) * 20_000)

  use_ai = False
  if gen.is_generative_ai_available() and not (edit_mode and description):
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    use_ai = Confirm.ask(f"[blue]󰫢 [/]{provider.title()} AI is available. Generate description and results?", default=False)

  if use_ai:
    entry_title = sub_entry.get("title") if sub_entry else None
    sub_entry_fields = {
      "date": activity_datetime,
      "duration": duration,
      "target": target,
      "audience": audience,
      "budget": budget,
    }
    while True:
      desc_prompt = gen.generate_description_prompt(program_title, sub_entry_title, entry_title=entry_title, sub_entry_fields=sub_entry_fields)
      console.print(Panel(Markdown(desc_prompt), title="Current Prompt"))
      if Confirm.ask("Add additional context?", default=False):
        context = Prompt.ask("Enter additional context")
        desc_prompt = gen.generate_description_prompt(program_title, sub_entry_title, context, entry_title=entry_title, sub_entry_fields=sub_entry_fields)

      with console.status("[blue]Generating description...[/]"):
        generated_desc = gen.generate_content(desc_prompt)

      result_prompt = gen.generate_result_prompt(program_title, sub_entry_title, generated_desc, entry_title=entry_title, sub_entry_fields=sub_entry_fields)
      with console.status("[blue]Generating result...[/]"):
        generated_result = gen.generate_content(result_prompt)
      if len(generated_result) > 256:
        generated_result = generated_result[:253] + "..."

      generated_content = f"Deskripsi kegiatan:\n{generated_desc}\nHasil Kegiatan:\n{generated_result}"
      console.print(Panel(generated_content, title="AI Generated Content"))

      choice = Prompt.ask("Accept (a), Regenerate (r), or write Manually (m)?", choices=["a", "r", "m"], default="a")
      if choice == "r":
        continue
      elif choice == "m":
        description = input("\nEnter Acticity Description: ")
        result = input("Enter Activity Result: ")
        break
      else:
        description, result = generated_desc, generated_result
        break
  elif not description:
    description = input("\nEnter Acticity Description: ")
    result = input("Enter Activity Result: ")

  form_data = Table(box=box.ROUNDED, title="Summary")
  form_data.add_column(Align.center("Field"), style="bold #89dceb")
  form_data.add_column(Align.center("Content"), overflow="fold")

  form_data.add_row("Title", sub_entry_title)
  form_data.add_row("Date", activity_datetime)
  form_data.add_row("Duration", f"{duration} minutes")
  form_data.add_row("Target", target)
  form_data.add_row("Audience", f"{audience} people")
  form_data.add_row("JOK", f"Rp. {jok}")
  form_data.add_row("Description", description)
  form_data.add_row("Budget source", "UGM")
  form_data.add_row("Budget", budget)
  form_data.add_row("Result", result)

  console.print(form_data)
  confirm_text = "Do you want to update this entry?" if edit_mode else "Do you want to add this entry?"
  confirm = Confirm.ask(confirm_text, default=True)

  if not confirm:
    console.print("Operation cancelled.")
    return

  return_url = sub_entry.get("activity_url") if sub_entry else None

  return return_url, {
    "title": sub_entry_title,
    "datetime": activity_datetime,
    "duration": int(duration),
    "target": target,
    "jok": jok,
    "audience": audience,
    "description": description,
    "budget": budget,
    "result": result,
  }
