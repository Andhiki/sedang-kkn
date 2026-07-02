import asyncio
import os

import httpx
from prompt_toolkit import HTML
from rich.prompt import Prompt

from datatypes import EntryData
from ui.prompt import get_entry_details_from_user, get_sub_entry_details_from_user, parse_selection
from ui.tables import print_assisted_program, print_program_details, print_program_title, print_unattended_program
from rich.table import Table
from rich import box

from ui.tui import console, print_log
from utils.common import async_input, generate_random_points, load_background
from utils.kkn import KKN
from utils.simaster import Simaster


def _filter_unattended_program(data: dict | None, source: str = "assisted") -> list[dict]:
  if not data:
    print_log(f"No {source} program found", "ERROR")
    return []

  filtered_program = []

  for key, value in data.items():
    if isinstance(value, dict):
      entries = value.get("entries", [])
      base_info = {"title": value.get("title"), "type": "main", "id": key}
    else:
      entries = value
      base_info = {"pic": key, "type": "bantu"}

    for entry in entries or []:
      for sub in entry.get("sub_entries", []):
        if not (url := sub.get("attendance_link")):
          continue
        if sub.get("is_attended"):
          continue

        info = {**base_info, "entry": entry.get("title"), "sub_entry": sub.get("title"), "url": url, "date": sub.get("date")}
        filtered_program.append(info)

  return filtered_program


async def show_all_program(kkn: KKN):
  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)
  await print_program_details(kkn.main_program)
  await print_assisted_program(kkn.assisted_program)


async def _select_program(kkn: KKN) -> str | None:
  await print_program_title(kkn.main_program)
  p_ids = list(kkn.main_program.keys())
  if not p_ids:
    print_log("No main programs found", "ERROR")
    return None

  try:
    choice = await async_input(
      HTML(
        f'Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(p_ids)}</num>) '
        f'<choice fg="ansimagenta">[{"/".join(str(i + 1) for i in range(len(p_ids)))}]</choice>: </delim>'
      ),
      int,
    )
  except ValueError:
    print_log("Invalid program choice", "ERROR")
    return None

  if choice < 1 or choice > len(p_ids):
    print_log("Invalid program choice", "ERROR")
    return None

  return p_ids[choice - 1]


async def manage_entry(kkn: KKN):
  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  p_id = await _select_program(kkn)
  if not p_id:
    return

  program = kkn.main_program[p_id]
  entries = program.get("entries", [])
  if not entries:
    print_log("No entries found for this program", "ERROR")
    return

  table = Table(box=box.ROUNDED, title=f"Program Utama — {program.get('title', 'N/A')}")
  table.add_column("No", justify="center", style="#fab387", width=2)
  table.add_column("Entry", style="#89b4fa")
  table.add_column("Date", justify="center", style="#89b4fa")
  table.add_column("Location", style="#cdd6f4")

  for i, entry in enumerate(entries, 1):
    table.add_row(str(i), entry.get("title", "N/A"), entry.get("date", "N/A"), entry.get("location", "N/A"))
  console.print(table)

  try:
    choice = await async_input(
      HTML(
        f'Enter entry choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(entries)}</num>): </delim>'
      ),
      int,
    )
  except ValueError:
    print_log("Invalid entry choice", "ERROR")
    return

  if choice < 1 or choice > len(entries):
    print_log("Invalid entry choice", "ERROR")
    return

  selected_entry = entries[choice - 1]
  edit_url = selected_entry.get("edit_url")

  mode = Prompt.ask("Mode: (e)dit existing, (a)dd new, (c)ancel", choices=["e", "a", "c"], default="a")
  if mode == "c":
    return

  if mode == "e":
    if not edit_url:
      print_log("No edit URL available for this entry (may be locked).", "ERROR")
      return
  else:
    edit_url = None

  data = get_entry_details_from_user(
    kkn.main_program[p_id],
    edit_mode=(mode == "e"),
    existing=selected_entry,
  )
  if data:
    await kkn.add_logbook_entry(p_id, data, edit_url=edit_url)
    kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id]))


async def manage_sub_entry(kkn: KKN):
  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  p_id = await _select_program(kkn)
  if not p_id:
    return

  program = kkn.main_program[p_id]
  entries = program.get("entries", [])
  if not entries:
    print_log("No entries found for this program", "ERROR")
    return

  table = Table(box=box.ROUNDED, title=f"Program Utama — {program.get('title', 'N/A')}")
  table.add_column("No", justify="center", style="#fab387", width=2)
  table.add_column("Entry", style="#89b4fa")
  table.add_column("Date", justify="center", style="#89b4fa")

  for i, entry in enumerate(entries, 1):
    table.add_row(str(i), entry.get("title", "N/A"), entry.get("date", "N/A"))
  console.print(table)

  try:
    entry_choice = await async_input(
      HTML(
        f'Enter entry choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(entries)}</num>): </delim>'
      ),
      int,
    )
  except ValueError:
    print_log("Invalid entry choice", "ERROR")
    return

  if entry_choice < 1 or entry_choice > len(entries):
    print_log("Invalid entry choice", "ERROR")
    return

  selected_entry = entries[entry_choice - 1]
  sub_entries = selected_entry.get("sub_entries", [])

  sub_table = Table(box=box.ROUNDED, title=f"Sub-entries — {selected_entry.get('title', 'N/A')}")
  sub_table.add_column("No", justify="center", style="#fab387", width=2)
  sub_table.add_column("Sub-entry", style="#89b4fa")
  sub_table.add_column("Date", justify="center", style="#89b4fa")
  sub_table.add_column("Status", justify="center")

  for i, sub in enumerate(sub_entries, 1):
    status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "Belum Presensi")
    sub_table.add_row(str(i), sub.get("title", "N/A"), sub.get("date", "N/A"), status)
  console.print(sub_table)

  mode = Prompt.ask("Mode: (e)dit existing, (a)dd new, (c)ancel", choices=["e", "a", "c"], default="e")
  if mode == "c":
    return

  existing_sub = None
  edit_url = None
  if mode == "e":
    if not sub_entries:
      print_log("No sub-entries to edit", "ERROR")
      return
    try:
      sub_choice = await async_input(
        HTML(
          f'Enter sub-entry choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(sub_entries)}</num>): </delim>'
        ),
        int,
      )
    except ValueError:
      print_log("Invalid sub-entry choice", "ERROR")
      return
    if sub_choice < 1 or sub_choice > len(sub_entries):
      print_log("Invalid sub-entry choice", "ERROR")
      return
    existing_sub = sub_entries[sub_choice - 1]
    edit_url = existing_sub.get("edit_url")
    if not edit_url:
      print_log("No edit URL available for this sub-entry (may be locked).", "ERROR")
      return

  try:
    result = get_sub_entry_details_from_user(
      kkn.main_program[p_id],
      edit_mode=(mode == "e"),
      entry=selected_entry,
      existing_sub=existing_sub,
    )
    if result:
      await kkn.add_logbook_sub_entry(result[0] or "", result[1], edit_url=edit_url)
      kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id], pool_size=2))
  except KeyboardInterrupt:
    return


async def handle_unattended_entries(kkn: KKN):
  try:
    default_lat = float(os.getenv("KKN_LOCATION_LATITUDE", ""))
    default_long = float(os.getenv("KKN_LOCATION_LONGITUDE", ""))
    radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", ""))
  except (TypeError, ValueError):
    print_log(
      "Either one of the following is not set correctly in .env file:"
      "\n[#fab387]1[/][#89dceb].[white] KKN_LOCATION_LATITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]2[/][#89dceb].[white] KKN_LOCATION_LONGITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]3[/][#89dceb].[white] QR_CODE_VALUE[/]:[/] [yellow]int[/]"
    )
    return

  await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

  unattended_main = _filter_unattended_program(kkn.main_program, source="main")
  unattended_assisted = _filter_unattended_program(kkn.assisted_program, source="assisted")
  unattended = [*unattended_main, *unattended_assisted]

  if not unattended:
    print_log("No unattended programs found!")
    return

  await print_unattended_program(unattended)
  indices = await async_input(
    HTML(
      'Enter indices to process <delim fg="#89dceb">(<num fg="#a6e3a1">"1 2 3"<dash fg="#89dceb"> or </dash>"1-4"</num>): </delim>'
    ),
    parse_selection,
  )

  unattended_len = len(unattended)
  final_indices = [i for i in indices if i <= unattended_len]

  id_to_update = set()
  update_assisted = False
  for id in final_indices:
    item = unattended[id - 1]
    entry = item.get("sub_entry")
    console.print(f"Sending attendance for {entry}...")

    latitude, longitude = generate_random_points(default_lat, default_long, radius)
    if await kkn.post_logbook_attendance(item.get("url"), latitude, longitude):
      if item.get("type") == "bantu":
        update_assisted = True
      else:
        id_to_update.add(item.get("id"))

  kkn.loader = asyncio.create_task(
    kkn.update_logbook_entries(kkn.simaster_account, list(id_to_update), len(id_to_update) + 1, update_assisted)
  )


async def change_account() -> tuple[Simaster, httpx.AsyncClient, KKN] | None:
  new_username = await async_input(HTML('Username<delim fg="#89dceb">:</delim> '))
  new_password = await async_input(HTML('Password<delim fg="#89dceb">:</delim> '), is_password=True)

  new_simaster = Simaster(new_username, new_password)
  if new_session := await new_simaster.login(verbose=True):
    new_kkn = KKN(new_session, new_simaster)
    return new_simaster, new_session, new_kkn

  return None
