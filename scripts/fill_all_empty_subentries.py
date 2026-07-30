"""Fill all empty sub-entries across DKDHIKI programs in SIMASTER."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

from utils.kkn import KKN
from utils.simaster import Simaster

load_dotenv()

DEFAULT_AUDIENCE = "2"
DEFAULT_BUDGET = "0"
DEFAULT_SOURCE = ["1"]  # UGM

def make_desc_result(program: str, entry: str, sub: str, target: str, duration: int) -> tuple[str, str]:
  """Return (description, result) for a sub-entry."""
  # Tailored by program theme
  if "Atlas" in program:
    context = "portal data dan informasi desa"
    audience_word = "pemerintah desa dan masyarakat"
  elif "Explorer" in program:
    context = "peta interaktif wisata dan layanan lokal"
    audience_word = "wisatawan dan pelaku UMKM"
  elif "Compass" in program:
    context = "sistem rekomendasi wisata berbasis preferensi pengunjung"
    audience_word = "wisatawan"
  elif "Stories" in program:
    context = "arsip digital budaya, sejarah, dan cerita lokal"
    audience_word = "masyarakat dan wisatawan"
  elif "Cerdas Digital" in program:
    context = "edukasi literasi dan keamanan digital"
    audience_word = "siswa SMP dan masyarakat"
  else:
    context = "program kerja KKN"
    audience_word = "masyarakat"

  desc = (
    f"Kegiatan '{sub}' merupakan bagian dari tahapan '{entry}' dalam program kerja "
    f"'{program}'. Kegiatan ini dilaksanakan untuk mendukung {context} dengan sasaran "
    f"{target}. Selama {duration} menit, tim pelaksana melakukan aktivitas sesuai fokus sub-tahapan, "
    f"mencatat temuan, dan berkoordinasi dengan {audience_word} terkait."
  )
  result = (
    f"Sub-tahapan '{sub}' telah berhasil dilaksanakan dengan lancar. "
    f"Hasil yang dicapai mendukung kelanjutan tahapan '{entry}' dan program kerja '{program}'."
  )
  return desc, result


# Map of program title keyword -> list of entry updates
ALL_UPDATES = {
  "Atlas": [
    {
      "entry_index": 6,
      "title": "Pelaporan dan Dokumentasi",
      "date": "2026-07-29",
      "sub_entries": [
        {
          "title": "Penyusunan Laporan & Dokumentasi",
          "datetime": "2026-07-29 08:00",
          "duration": 120,
          "target": "Internal Kelompok & Pemerintah Desa",
        },
      ],
    },
    {
      "entry_index": 7,
      "title": "Evaluasi dan Rencana Maintenance",
      "date": "2026-07-29",
      "sub_entries": [
        {
          "title": "Evaluasi Sistem & Rencana Pemeliharaan",
          "datetime": "2026-07-29 11:00",
          "duration": 180,
          "target": "Internal Kelompok",
        },
      ],
    },
  ],
  "Explorer": [
    {
      "entry_index": 8,
      "title": "Pelaporan Hasil Kegiatan",
      "date": "2026-07-29",
      "sub_entries": [
        {
          "title": "Penyusunan Laporan",
          "datetime": "2026-07-29 14:00",
          "duration": 120,
          "target": "Internal Kelompok & Stakeholder",
        },
      ],
    },
    {
      "entry_index": 9,
      "title": "Evaluasi Kegiatan",
      "date": "2026-07-29",
      "sub_entries": [
        {
          "title": "Evaluasi Akhir",
          "datetime": "2026-07-29 19:00",
          "duration": 180,
          "target": "Internal Kelompok",
        },
      ],
    },
  ],
  "Compass": [
    {
      "entry_index": 6,
      "title": "Pelaporan Hasil Kegiatan",
      "date": "2026-07-30",
      "sub_entries": [
        {
          "title": "Penyusunan Laporan",
          "datetime": "2026-07-30 08:00",
          "duration": 120,
          "target": "Internal Kelompok & Dosen Pembimbing",
        },
      ],
    },
    {
      "entry_index": 7,
      "title": "Evaluasi Kegiatan",
      "date": "2026-07-30",
      "sub_entries": [
        {
          "title": "Evaluasi Bersama",
          "datetime": "2026-07-30 11:00",
          "duration": 90,
          "target": "Internal Kelompok",
        },
        {
          "title": "Penyusunan Rekomendasi",
          "datetime": "2026-07-30 12:30",
          "duration": 90,
          "target": "Internal Kelompok",
        },
      ],
    },
  ],
  "Stories": [
    {
      "entry_index": 5,
      "title": "Publikasi dan Optimasi SEO",
      "date": "2026-07-30",
      "sub_entries": [
        {
          "title": "Publikasi Konten",
          "datetime": "2026-07-30 15:00",
          "duration": 120,
          "target": "Masyarakat & Wisatawan",
        },
        {
          "title": "Optimisasi SEO",
          "datetime": "2026-07-30 18:00",
          "duration": 120,
          "target": "Masyarakat & Wisatawan",
        },
      ],
    },
  ],
  "Cerdas Digital": [
    {
      "entry_index": 6,
      "title": "Dokumentasi Internal Kegiatan",
      "date": "2026-07-31",
      "sub_entries": [
        {
          "title": "Arsip Foto dan Video Pos",
          "datetime": "2026-07-31 12:00",
          "duration": 150,
          "target": "Internal Kelompok Pos 5",
        },
        {
          "title": "Catatan Lapangan dari Pos",
          "datetime": "2026-07-31 14:30",
          "duration": 150,
          "target": "Internal Kelompok Pos 5",
        },
        {
          "title": "Pengumpulan Leaflet dan Hasil Kerja Siswa",
          "datetime": "2026-07-31 17:00",
          "duration": 150,
          "target": "Siswa SMP & Internal Kelompok Pos 5",
        },
      ],
    },
    {
      "entry_index": 7,
      "title": "Refleksi & Pengembangan Bahan Pos",
      "date": "2026-08-01",
      "sub_entries": [
        {
          "title": "Diskusi Evaluasi Respon Siswa di Pos 5",
          "datetime": "2026-08-01 08:00",
          "duration": 120,
          "target": "Internal Kelompok Pos 5",
        },
        {
          "title": "Revisi Leaflet dan Soal Interaktif",
          "datetime": "2026-08-01 11:00",
          "duration": 120,
          "target": "Siswa SMP & Internal Kelompok Pos 5",
        },
        {
          "title": "Penyusunan Panduan Pos",
          "datetime": "2026-08-01 13:00",
          "duration": 120,
          "target": "Internal Kelompok Pos 5",
        },
      ],
    },
    {
      "entry_index": 8,
      "title": "Pelaporan Internal Outbound",
      "date": "2026-08-01",
      "sub_entries": [
        {
          "title": "Penyusunan Laporan Internal Outbound",
          "datetime": "2026-08-01 16:00",
          "duration": 120,
          "target": "Internal Kelompok & Dosen Pembimbing",
        },
      ],
    },
    {
      "entry_index": 9,
      "title": "Evaluasi Kegiatan Outbound",
      "date": "2026-08-01",
      "sub_entries": [
        {
          "title": "Evaluasi dan Refleksi Kegiatan Outbound Pos",
          "datetime": "2026-08-01 19:00",
          "duration": 120,
          "target": "Internal Kelompok Pos 5",
        },
      ],
    },
  ],
}


def build_sub_payload(program_title: str, entry_title: str, sub: dict) -> dict:
  audience = DEFAULT_AUDIENCE
  duration = sub["duration"]
  jok = int(int(audience) * (duration / 60) * 20_000)
  desc, result = make_desc_result(program_title, entry_title, sub["title"], sub["target"], duration)
  return {
    "title": sub["title"],
    "datetime": sub["datetime"],
    "duration": duration,
    "target": sub["target"],
    "jok": jok,
    "audience": audience,
    "description": desc,
    "budget": DEFAULT_BUDGET,
    "result": result,
  }


async def main(dry_run: bool = False):
  username = os.getenv("SIMASTER_USERNAME")
  password = os.getenv("SIMASTER_PASSWORD")
  if not username or not password:
    print("SIMASTER_USERNAME/PASSWORD not found in .env")
    return 1

  default_lat = float(os.getenv("KKN_LOCATION_LATITUDE", "-5.878634"))
  default_long = float(os.getenv("KKN_LOCATION_LONGITUDE", "110.434331"))

  simaster = Simaster(username, password)
  client = await simaster.login(verbose=True)
  if not client:
    print("Login failed. Cache may be expired — run the TUI once to refresh.")
    return 1

  kkn = KKN(client, simaster)
  await kkn.loader

  # Find matching programs
  program_map = {}
  for keyword in ALL_UPDATES.keys():
    for p_id, prog in kkn.main_program.items():
      if keyword in prog.get("title", "") and p_id not in program_map.values():
        program_map[keyword] = p_id
        break

  missing = [kw for kw in ALL_UPDATES.keys() if kw not in program_map]
  if missing:
    print(f"Programs not found: {missing}")
    return 1

  print(f"\nMode: {'DRY RUN' if dry_run else 'LIVE'}")
  print(f"Location: {default_lat}, {default_long}")

  for keyword, specs in ALL_UPDATES.items():
    p_id = program_map[keyword]
    program = kkn.main_program[p_id]
    title = program.get("title", "N/A")
    entries = {e.get("entry_index"): e for e in program.get("entries", [])}

    print(f"\n{'='*80}")
    print(f"PROGRAM: {title} ({p_id})")
    print(f"{'='*80}")

    for spec in specs:
      idx = spec["entry_index"]
      entry = entries.get(idx)
      if not entry:
        print(f"\n[!] Entry #{idx} not found, skipping")
        continue

      print(f"\n[Entry #{idx}] {entry.get('title')} -> {spec['title']} | {spec['date']}")
      print(f"  edit_url: {entry.get('edit_url')}")
      print(f"  activity_url: {entry.get('activity_url')}")

      total_minutes = sum(s["duration"] for s in spec["sub_entries"])
      print(f"  sub-entries: {len(spec['sub_entries'])} | total: {total_minutes} menit")
      for sub in spec["sub_entries"]:
        payload = build_sub_payload(title, spec["title"], sub)
        print(f"    + {sub['title']}")
        print(f"      datetime: {sub['datetime']} | duration: {sub['duration']} menit")
        print(f"      target: {payload['target']} | audience: {payload['audience']} | jok: Rp{payload['jok']:,}")
        print(f"      budget: Rp{payload['budget']} | source: UGM")

      if dry_run:
        continue

      # Update entry title/date
      if not entry.get("edit_url"):
        print(f"  [!] No edit_url available, skipping entry update")
        continue

      ok_entry = await kkn.add_logbook_entry(
        p_id,
        {"title": spec["title"], "date": spec["date"], "latitude": default_lat, "longitude": default_long},
        edit_url=entry["edit_url"],
      )
      print(f"  Entry update: {'OK' if ok_entry else 'FAILED'}")

      # Refresh to get latest activity_url
      await kkn.update_logbook_entries(programs=[p_id], pool_size=2)
      entry = next((e for e in kkn.main_program[p_id]["entries"] if e.get("entry_index") == idx), None)
      if not entry or not entry.get("activity_url"):
        print(f"  [!] Could not get activity_url after update, skipping sub-entries")
        continue

      # Insert sub-entries
      for sub in spec["sub_entries"]:
        ok_sub = await kkn.add_logbook_sub_entry(entry["activity_url"], build_sub_payload(title, spec["title"], sub))
        print(f"  Sub-entry '{sub['title']}': {'OK' if ok_sub else 'FAILED'}")
        await asyncio.sleep(0.5)

      # Refresh after entry group
      await kkn.update_logbook_entries(programs=[p_id], pool_size=2)

  await client.aclose()
  return 0


if __name__ == "__main__":
  dry = "--dry-run" in sys.argv
  sys.exit(asyncio.run(main(dry_run=dry)))
