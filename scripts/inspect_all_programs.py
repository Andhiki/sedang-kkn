"""Inspect all DKDHIKI programs state in SIMASTER (read-only)."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

from utils.kkn import KKN
from utils.simaster import Simaster

load_dotenv()


async def main():
  username = os.getenv("SIMASTER_USERNAME")
  password = os.getenv("SIMASTER_PASSWORD")
  if not username or not password:
    print("SIMASTER_USERNAME/PASSWORD not found in .env")
    return 1

  simaster = Simaster(username, password)
  client = await simaster.login(verbose=True)
  if not client:
    print("Login failed.")
    return 1

  kkn = KKN(client, simaster)
  await kkn.loader

  if not kkn.main_program:
    print("No main programs found.")
    return 0

  # Sort by title to match DK11-DK59 order roughly
  programs = sorted(kkn.main_program.items(), key=lambda x: x[1].get("title", ""))

  for p_id, prog in programs:
    title = prog.get("title", "N/A")
    entries = prog.get("entries", [])

    # Calculate total hours from sub-entries
    total_minutes = 0
    attended_minutes = 0
    for e in entries:
      for sub in e.get("sub_entries", []):
        dur_str = sub.get("duration", "N/A")
        val = 0
        if dur_str and dur_str != "N/A":
          import re
          m = re.search(r"[\d.]+", str(dur_str))
          if m:
            num = float(m.group())
            if "menit" in str(dur_str).lower():
              val = num
            else:
              val = num * 60
        total_minutes += val
        if sub.get("is_attended"):
          attended_minutes += val

    total_hours = total_minutes / 60
    attended_hours = attended_minutes / 60

    print(f"\n{'='*80}")
    print(f"PROGRAM: {title}")
    print(f"ID: {p_id} | Total: {total_hours:.1f} jam | Sudah Presensi: {attended_hours:.1f} jam")
    print(f"{'='*80}")

    for e in entries:
      status = e.get("attendance_status", "Belum Presensi")
      print(f"\n  Entry #{e.get('entry_index')}: {e.get('title')}")
      print(f"    Date: {e.get('date')} | Status: {status}")
      if not e.get("sub_entries"):
        print("    [KOSONG — belum ada sub-entry]")
      for sub in e.get("sub_entries", []):
        icon = "✅" if sub.get("is_attended") else "☐"
        print(f"    {icon} {sub.get('title')} | {sub.get('date')} | {sub.get('duration')} | {sub.get('status')}")

  await client.aclose()
  return 0


if __name__ == "__main__":
  sys.exit(asyncio.run(main()))
