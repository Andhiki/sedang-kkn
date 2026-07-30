import os
import re
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from rich import box
from rich.align import Align
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

import utils.generative as gen
from datatypes import AnggotaData, EntryData, LogEntryPayload, RPPData, SubEntryData
from ui.tables import print_program_entries, print_program_sub_entries
from ui.tui import console, print_log
from utils.common import generate_random_points

ID_MONTHS = {
  "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
  "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def _id_date_to_iso(date_str: str) -> str:
  """Convert Indonesian long date (e.g. 'Rabu, 29 Juli 2026') to 'YYYY-MM-DD'.

  Falls back to today's date on failure.
  """
  if not date_str:
    return datetime.now().strftime("%Y-%m-%d")
  s = date_str.strip()
  # Strip leading weekday if present (e.g. "Rabu, 29 Juli 2026")
  if "," in s:
    s = s.split(",", 1)[1].strip()
  parts = s.split()
  if len(parts) == 3:
    try:
      day = int(parts[0])
      month = ID_MONTHS.get(parts[1].lower())
      year = int(parts[2])
      if month:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
      pass
  # Already ISO-ish
  if re.match(r"\d{4}-\d{2}-\d{2}", s):
    return s[:10]
  return datetime.now().strftime("%Y-%m-%d")


class AnggotaCompleter(Completer):
  """Fuzzy-ish searchable completer for anggota. Matches name/nim/kelompok."""

  def __init__(self, anggota: list[AnggotaData]):
    self.anggota = anggota

  def get_completions(self, document, complete_event):
    word = document.get_word_before_cursor().lower()
    if not word:
      for a in self.anggota:
        yield Completion(
          a["mhs_id"],
          display=a["name"],
          display_meta=f"{a['nim']} · {a['kelompok']}",
        )
      return
    for a in self.anggota:
      hay = f"{a['name']} {a['nim']} {a['kelompok']}".lower()
      if word in hay:
        yield Completion(
          a["mhs_id"],
          display=a["name"],
          display_meta=f"{a['nim']} · {a['kelompok']}",
        )


async def select_anggota(
  anggota: list[AnggotaData],
  pre_selected: list[str] | None = None,
) -> list[str]:
  """Interactive multi-select anggota with searchable dropdown.

  Returns list of selected mhs_id values.
  """
  if not anggota:
    console.print("[yellow]No anggota available.[/]")
    return []

  pre_selected = pre_selected or []
  selected: list[str] = list(pre_selected)

  id_to_anggota = {a["mhs_id"]: a for a in anggota}

  def render_selected():
    if not selected:
      console.print("[dim]No anggota selected.[/]")
      return
    tbl = Table(box=box.SIMPLE, title="Selected Anggota", title_style="bold #a6e3a1")
    tbl.add_column("#", justify="right", style="#fab387", width=3)
    tbl.add_column("Name", style="#cdd6f4")
    tbl.add_column("NIM", style="#89b4fa")
    tbl.add_column("Kelompok", style="#f9e2af")
    for i, mid in enumerate(selected, 1):
      a = id_to_anggota.get(mid)
      if a:
        tbl.add_row(str(i), a["name"], a["nim"], a["kelompok"])
    console.print(tbl)

  console.print(
    f"[blue]Anggota selection.[/] [dim]{len(anggota)} available. "
    "Type to search (name/NIM/kelompok), Enter to add. "
    "'list' to show selected, 'del <n>' to remove, 'done' to finish.[/]"
  )

  completer = AnggotaCompleter(anggota)
  session = PromptSession(completer=completer)

  while True:
    render_selected()
    try:
      raw = await session.prompt_async("anggota> ")
    except (KeyboardInterrupt, EOFError):
      break

    line = raw.strip()
    if not line:
      continue
    if line.lower() in ("done", "selesai", "ok", "q"):
      break
    if line.lower() in ("list", "show", "ls"):
      continue
    if line.lower().startswith(("del ", "rm ", "remove ")):
      parts = line.split()
      if len(parts) >= 2 and parts[1].isdigit():
        idx = int(parts[1]) - 1
        if 0 <= idx < len(selected):
          removed = selected.pop(idx)
          a = id_to_anggota.get(removed)
          console.print(f"[red]Removed[/] {a['name'] if a else removed}")
        else:
          console.print(f"[red]Invalid index: {parts[1]}[/]")
      continue
    if line.lower() in ("clear", "reset"):
      selected.clear()
      console.print("[red]Cleared all selected.[/]")
      continue
    if line.lower() in ("all", "selectall"):
      selected = [a["mhs_id"] for a in anggota]
      console.print(f"[green]Selected all {len(selected)} anggota.[/]")
      continue

    tokens = line.split()
    added_any = False
    for tok in tokens:
      if tok in id_to_anggota:
        if tok not in selected:
          selected.append(tok)
          a = id_to_anggota[tok]
          console.print(f"[green]Added[/] {a['name']} ({a['nim']})")
          added_any = True
        else:
          console.print(f"[yellow]Already selected:[/] {tok}")
      else:
        matches = [a for a in anggota if tok.lower() in f"{a['name']} {a['nim']}".lower()]
        if len(matches) == 1:
          mid = matches[0]["mhs_id"]
          if mid not in selected:
            selected.append(mid)
            console.print(f"[green]Added[/] {matches[0]['name']} ({matches[0]['nim']})")
            added_any = True
          else:
            console.print(f"[yellow]Already selected:[/] {matches[0]['name']}")
        elif len(matches) > 1:
          console.print(f"[yellow]Ambiguous '{tok}', {len(matches)} matches. Be more specific:[/]")
          for a in matches[:5]:
            console.print(f"  {a['mhs_id']} → {a['name']} ({a['nim']}) [{a['kelompok']}]")
        else:
          console.print(f"[red]No match for '{tok}'. Use Tab to autocomplete mhs_id.[/]")

    if not added_any:
      continue

  return selected


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


async def get_entry_details_from_user(
  data: RPPData,
  edit_mode: bool = False,
  existing: dict | None = None,
  anggota: list[AnggotaData] | None = None,
  pre_selected_anggota: list[str] | None = None,
) -> LogEntryPayload | None:
  console.print(f"\nCurrent entries for [bold blue]{data['title']}")
  print_program_entries(data)

  default_title = existing.get("title", "") if (edit_mode and existing) else ""
  default_date = (
    _id_date_to_iso(existing.get("date", ""))
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

  selected_anggota: list[str] = []
  if anggota:
    add_anggota = Confirm.ask("Pilih anggota untuk tahapan ini?", default=True)
    if add_anggota:
      selected_anggota = await select_anggota(anggota, pre_selected=pre_selected_anggota)

  form_data = Table(box=box.ROUNDED, title="Summary")
  form_data.add_column(Align.center("Field"), style="bold #89dceb")
  form_data.add_column(Align.center("Content"), overflow="fold")

  form_data.add_row("Title", entry_title)
  form_data.add_row("Date", activity_datetime)

  location = Table(box=box.ROUNDED, show_header=False)
  location.add_row("[bold]Latitude", f"[#fab387]{latitude}")
  location.add_row("[bold]Longitude", f"[#fab387]{longitude}")

  form_data.add_row("Location", location)

  if anggota:
    id_to_anggota = {a["mhs_id"]: a for a in anggota}
    if selected_anggota:
      names = "\n".join(
        f"• {id_to_anggota[mid]['name']} ({id_to_anggota[mid]['nim']})" for mid in selected_anggota if mid in id_to_anggota
      )
    else:
      names = "[dim]None[/]"
    form_data.add_row("Anggota", names)

  console.print(form_data)
  confirm_text = "Do you want to update this entry?" if edit_mode else "Do you want to add this entry?"
  confirm = Confirm.ask(confirm_text, default=True)

  if not confirm:
    console.print("Operation cancelled.")
    return

  random_lat, random_long = generate_random_points(latitude, longitude, 15)

  return {
    "title": entry_title,
    "date": activity_datetime,
    "longitude": longitude,
    "latitude": latitude,
    "anggota": selected_anggota,
  }


def _parse_duration(value: str) -> str:
  match = re.search(r"\d+", value)
  return match.group(0) if match else "60"


def _parse_datetime(value: str) -> tuple[str, str]:
  """Return (date, time) from strings like '2025-07-02 09:00' or 'Rabu, 29 Juli 2026 09:00'."""
  now = datetime.now()
  default_date = now.strftime("%Y-%m-%d")
  default_time = now.strftime("%H:%M")
  if not value:
    return default_date, default_time

  s = value.strip()
  # Extract time (HH:MM) if present
  time_match = re.search(r"\d{2}:\d{2}", s)
  time_str = time_match.group(0) if time_match else default_time
  # Remove time from string for date parsing
  s_no_time = s[: time_match.start()] if time_match else s

  # Try Indonesian long date: "Rabu, 29 Juli 2026" or "29 Juli 2026"
  id_match = re.search(
    r"(\d{1,2})\s+(" + "|".join(ID_MONTHS.keys()) + r")\s+(\d{4})", s_no_time, re.IGNORECASE
  )
  if id_match:
    day = int(id_match.group(1))
    month = ID_MONTHS[id_match.group(2).lower()]
    year = int(id_match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}", time_str

  # Try ISO date
  iso_match = re.search(r"\d{4}-\d{2}-\d{2}", s_no_time)
  if iso_match:
    return iso_match.group(0), time_str

  return default_date, time_str


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
