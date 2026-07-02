import os
import re

from rich import box
from rich.align import Align
from rich.box import Box
from rich.panel import Panel
from rich.table import Table

from datatypes import AssistedProgram, EntryData, RPPData
from ui.tui import console, print_log


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

# fmt: off
ROUNDED_HOLLOW: Box = Box(
    "╭──╮\n"
    "│  │\n"
    "├──┤\n"
    "│  │\n"
    "├──┤\n"
    "├──┤\n"
    "│  │\n"
    "╰──╯\n"
)
# fmt: on


STATUS_COLORS = {"Sudah Presensi": "[green]", "Persetujuan DPL": "[yellow]", "Belum Presensi": "[red]"}


def _create_nested_table(data: EntryData | AssistedProgram, count: list[int] | None = None) -> Panel | Table:
  table = Table(box=ROUNDED_HOLLOW, expand=True)

  table.add_column(Align.center(data["title"]), style="#89b4fa", ratio=5)
  table.add_column("Duration", justify="center", style="#89b4fa", min_width=8)
  table.add_column("Status", justify="center", min_width=16)

  has_item = False
  for sub in data["sub_entries"]:
    has_item = True
    status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "-")
    title = sub.get("title")
    duration = sub.get("duration", "0")
    color = STATUS_COLORS.get(status, "")

    table.add_row(title, duration, f"{color}{status}")

    if count is not None and status == "Sudah Presensi":
      try:
        count.append(int(float(duration.split()[0])))
      except (ValueError, IndexError):
        pass

  if not has_item:
    table.box = None
    table.show_edge = False
    table.padding = 0
    return Panel(table)

  return table


async def _print_program_table_flat(title: str, data: dict, is_assisted: bool = False):
  """Print programs as a flat scrollable table (no nested tables)."""
  if not data:
    print_log(f"No data found for {title}")
    return

  table = Table(box=box.ROUNDED, title=title, expand=True)

  table.add_column("No", justify="center", style="#fab387", width=2)
  table.add_column("Program" if not is_assisted else "PIC", style="#89b4fa", ratio=2)
  table.add_column("Entry", style="#cdd6f4", ratio=2)
  table.add_column("Sub-entry", style="#cdd6f4", ratio=3)
  table.add_column("Duration", justify="center", style="#89b4fa", ratio=1)
  table.add_column("Status", justify="center", min_width=16)

  counter = 1
  total_hours = 0.0
  for key, value in data.items():
    program_label = key if is_assisted else value.get("title", "N/A")
    entries = value if is_assisted else value.get("entries", [])

    first_row = True
    for entry in entries:
      entry_title = entry.get("title", "N/A")
      entry_date = entry.get("date", "N/A")
      entry_cell = f"{entry_title}\n[dim]{entry_date}[/]"
      for sub in entry.get("sub_entries", []):
        status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "Belum Presensi")
        color = STATUS_COLORS.get(status, "")
        row_program = program_label if first_row else ""
        row_entry = entry_cell if first_row else ""
        sub_date = sub.get("date", "N/A")
        sub_cell = f"{sub.get('title', 'N/A')}\n[dim]{sub_date}[/]"
        total_hours += _parse_duration_hours(sub.get("duration", "N/A"))
        table.add_row(
          str(counter),
          row_program,
          row_entry,
          sub_cell,
          sub.get("duration", "N/A"),
          f"{color}{status}",
        )
        counter += 1
        first_row = False
        entry_cell = ""

      if not entry.get("sub_entries"):
        table.add_row(
          str(counter),
          program_label if first_row else "",
          entry_cell if first_row else "",
          "—",
          "—",
          "[dim]—[/]",
        )
        counter += 1
        first_row = False

  console.print(table)
  console.print(Panel(f"[bold #89dceb]Total jam tercatat:[/] {_format_hours(total_hours)}", expand=False))


async def _print_program_table(title: str, data: dict, is_assisted: bool = False):
  await _print_program_table_flat(title, data, is_assisted)


def _print_simple_list(data: list):
  if not data:
    console.print(Panel(Align.center("Empty")))
    return

  table = Table(box=box.ROUNDED)
  table.add_column("No", justify="center", style="#fab387", width=2)
  table.add_column(Align.center("Entries"))
  table.add_column(Align.center("Date"))

  for i, item in enumerate(data, 1):
    table.add_row(str(i), item.get("title", "N/A"), item.get("date", "N/A"))

  console.print(table)


def _generate_unattended_table(data: list, counter: int, is_assisted: bool = False):
  if not data:
    return

  table = Table(box=box.SIMPLE, show_edge=False, expand=True)
  table.add_column("No", justify="center", style="#fab387", width=2)
  table.add_column(Align.center("PIC" if is_assisted else "Program"), ratio=2)
  table.add_column(Align.center("Activity Details"), ratio=3)
  table.add_column(Align.center("Date"), justify="center", style="#89b4fa", ratio=2)

  for i, item in enumerate(data, 1):
    col_name = item.get("pic", "N/A") if is_assisted else item.get("title", "N/A")
    details = f"Entry: {item.get('entry', 'N/A')}\n[#89dceb]└──[/] {item.get('sub_entry')}"
    date_val = item.get("date") or "N/A"
    table.add_row(str(counter), col_name, details, date_val)
    counter += 1

  return table, counter


async def print_program_title(data: dict[str, RPPData] | None):
  if not data:
    print_log("No data found")
    return None

  table = Table(box=box.ROUNDED)

  table.add_column("No", justify="center", style="#fab387")
  table.add_column(Align.center("Title"))

  for i, (k, v) in enumerate(data.items(), 1):
    table.add_row(str(i), v.get("title", "N/A"))

  console.print(table)


async def print_unattended_program(data: list):
  if not data:
    print_log("No data found")
    return

  main_progs = [x for x in data if x.get("type") == "main"]
  assisted_progs = [x for x in data if x.get("type") == "bantu"]

  table = Table(box=box.ROUNDED, title="[bold red]Unattended Activities", show_header=False)

  counter = 1
  if main_progs and (res := _generate_unattended_table(main_progs, counter)):
    table.add_row(Align.center("Program Utama"))
    table.add_section()
    inner_table, counter = res
    table.add_row(inner_table)

  if assisted_progs and (res := _generate_unattended_table(assisted_progs, counter, is_assisted=True)):
    table.add_section()
    table.add_row(Align.center("Program Bantu"))
    table.add_section()
    inner_table, counter = res
    table.add_row(inner_table)

  console.print(table)


async def print_assisted_program(data: dict[str, list[AssistedProgram]] | None):
  await _print_program_table("Program Bantu", data or {}, is_assisted=True)


async def print_program_details(data: dict[str, RPPData] | None):
  await _print_program_table("Program Utama", data or {}, is_assisted=False)


def print_program_entries(data: RPPData):
  _print_simple_list(data.get("entries", []))


def print_program_sub_entries(data: EntryData):
  _print_simple_list(data.get("sub_entries", []))
