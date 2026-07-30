"""Inspect Karimunjawa Cerdas Digital program state in SIMASTER (read-only)."""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path so imports work when run directly
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
    print("Login failed. Cache may be expired — run the TUI once to refresh.")
    return 1

  kkn = KKN(client, simaster)
  await kkn.loader

  if not kkn.main_program:
    print("No main programs found.")
    return 0

  target_p_id = None
  target_program = None
  for p_id, prog in kkn.main_program.items():
    title = prog.get("title", "")
    if "Cerdas Digital" in title or "Literasi" in title or "Keamanan Digital" in title:
      target_p_id = p_id
      target_program = prog
      break

  if not target_program:
    print("Available programs:")
    for p_id, prog in kkn.main_program.items():
      print(f"  - {p_id}: {prog.get('title')}")
    print("\nTarget program not found. Check the title above.")
    return 0

  print(f"\n=== PROGRAM: {target_program.get('title')} ({target_p_id}) ===")
  entries = target_program.get("entries", [])
  if not entries:
    print("No entries yet.")
  for e in entries:
    print(f"\nEntry #{e.get('entry_index')}: {e.get('title')}")
    print(f"  Date: {e.get('date')} | Location: {e.get('location')} | Status: {e.get('attendance_status')}")
    for sub in e.get("sub_entries", []):
      status_icon = "✅" if sub.get("is_attended") else "☐"
      print(f"    {status_icon} {sub.get('title')} | {sub.get('date')} | {sub.get('duration')} | {sub.get('status')}")

  await client.aclose()
  return 0


if __name__ == "__main__":
  sys.exit(asyncio.run(main()))
