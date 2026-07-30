"""Auto-update DK56-DK59 entries and insert sub-entries for Karimunjawa Cerdas Digital."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

from utils.kkn import KKN
from utils.simaster import Simaster

load_dotenv()

# Updated DK56-DK59 definitions from latest Excel
DK56_59 = [
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
        "audience": "2",
        "description": "Mengumpulkan dan mengarsipkan dokumentasi visual berupa foto serta video selama kegiatan outbound literasi digital di pos 5, termasuk dokumentasi kegiatan siswa dan interaksi di lapangan.",
        "result": "Arsip foto dan video kegiatan pos 5 berhasil dikumpulkan untuk dokumentasi internal kelompok.",
      },
      {
        "title": "Catatan Lapangan dari Pos",
        "datetime": "2026-07-31 14:30",
        "duration": 150,
        "target": "Internal Kelompok Pos 5",
        "audience": "2",
        "description": "Menyusun catatan lapangan terkait pelaksanaan kegiatan di pos 5, mencakup observasi partisipasi siswa, kendala yang dihadapi, dan poin-poin penting selama penyampaian materi literasi digital.",
        "result": "Catatan lapangan pos 5 tersusun rapi dan menjadi bahan evaluasi serta perbaikan kegiatan.",
      },
      {
        "title": "Pengumpulan Leaflet dan Hasil Kerja Siswa",
        "datetime": "2026-07-31 17:00",
        "duration": 150,
        "target": "Siswa SMP & Internal Kelompok Pos 5",
        "audience": "2",
        "description": "Mengumpulkan leaflet, soal interaktif, dan hasil kerja siswa yang dihasilkan selama kegiatan outbound pos 5 untuk diarsipkan sebagai bahan evaluasi dan referensi kegiatan berikutnya.",
        "result": "Leaflet, soal, dan hasil kerja siswa pos 5 berhasil terkumpul dalam arsip internal kelompok.",
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
        "audience": "2",
        "description": "Melakukan diskusi internal kelompok pos 5 untuk mengevaluasi respon, partisipasi, dan pemahaman siswa SMP selama kegiatan outbound literasi digital berbasis leaflet dan soal interaktif.",
        "result": "Identifikasi kekuangan dan kelemahan penyampaian materi di pos 5 tercatat untuk bahan perbaikan.",
      },
      {
        "title": "Revisi Leaflet dan Soal Interaktif",
        "datetime": "2026-08-01 11:00",
        "duration": 120,
        "target": "Siswa SMP & Internal Kelompok Pos 5",
        "audience": "2",
        "description": "Merevisi desain leaflet dan soal interaktif pos 5 berdasarkan hasil evaluasi lapangan, dengan tujuan meningkatkan kualitas penyampaian materi literasi dan keamanan digital di kegiatan selanjutnya.",
        "result": "Leaflet dan soal interaktif pos 5 telah direvisi sesuai masukan dan observasi lapangan.",
      },
      {
        "title": "Penyusunan Panduan Pos",
        "datetime": "2026-08-01 13:00",
        "duration": 120,
        "target": "Internal Kelompok Pos 5",
        "audience": "2",
        "description": "Menyusun panduan singkat atau SOP pelaksanaan pos 5 sebagai acuan internal kelompok, agar kegiatan serupa di masa mendatang dapat berjalan lebih terstruktur dan efektif.",
        "result": "Panduan pelaksanaan pos 5 tersusun sebagai acuan internal untuk kegiatan berikutnya.",
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
        "audience": "2",
        "description": "Menyusun laporan internal mengenai pelaksanaan kegiatan outbound literasi digital pos 5, mencakup rangkaian kegiatan, dokumentasi, hasil observasi, dan evaluasi singkat.",
        "result": "Laporan internal pelaksanaan outbound literasi digital selesai disusun untuk dokumentasi kelompok.",
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
        "audience": "2",
        "description": "Melakukan evaluasi dan refleksi menyeluruh terhadap pelaksanaan kegiatan outbound literasi digital di pos 5, mencakup pencapaian, kendala, pembelajaran, dan rekomendasi perbaikan kegiatan.",
        "result": "Evaluasi kegiatan outbound pos 5 selesai dilakukan dengan rekomendasi perbaikan untuk program selanjutnya.",
      },
    ],
  },
]


def build_sub_payload(sub: dict) -> dict:
  audience = sub.get("audience", "2")
  duration = sub["duration"]
  jok = int(int(audience) * (duration / 60) * 20_000)
  return {
    "title": sub["title"],
    "datetime": sub["datetime"],
    "duration": duration,
    "target": sub.get("target", "Internal Kelompok"),
    "jok": jok,
    "audience": audience,
    "description": sub["description"],
    "budget": "0",
    "result": sub["result"],
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

  target_p_id = None
  for p_id, prog in kkn.main_program.items():
    if "Cerdas Digital" in prog.get("title", ""):
      target_p_id = p_id
      break

  if not target_p_id:
    print("Target program not found.")
    await client.aclose()
    return 1

  entries = kkn.main_program[target_p_id].get("entries", [])
  entry_by_index = {e.get("entry_index"): e for e in entries}

  print(f"\nProgram: {kkn.main_program[target_p_id].get('title')} ({target_p_id})")
  print(f"Location: {default_lat}, {default_long}")
  print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

  for spec in DK56_59:
    idx = spec["entry_index"]
    entry = entry_by_index.get(idx)
    if not entry:
      print(f"[!] Entry #{idx} not found, skipping")
      continue

    print(f"\n[Entry #{idx}] {entry.get('title')} -> {spec['title']} | {spec['date']}")
    print(f"  edit_url: {entry.get('edit_url')}")
    print(f"  activity_url: {entry.get('activity_url')}")

    total_minutes = sum(s["duration"] for s in spec["sub_entries"])
    print(f"  sub-entries: {len(spec['sub_entries'])} | total: {total_minutes} menit")
    for sub in spec["sub_entries"]:
      payload = build_sub_payload(sub)
      print(f"    + {sub['title']}")
      print(f"      datetime: {sub['datetime']} | duration: {sub['duration']} menit")
      print(f"      target: {payload['target']} | audience: {payload['audience']} | jok: Rp{payload['jok']:,}")
      print(f"      budget: Rp{payload['budget']} | source: UGM")
      print(f"      desc: {sub['description'][:80]}...")
      print(f"      result: {sub['result']}")

    if dry_run:
      continue

    # 1. Update entry title and date
    if not entry.get("edit_url"):
      print(f"  [!] No edit_url available, skipping entry update")
      continue

    ok_entry = await kkn.add_logbook_entry(
      target_p_id,
      {"title": spec["title"], "date": spec["date"], "latitude": default_lat, "longitude": default_long},
      edit_url=entry["edit_url"],
    )
    print(f"  Entry update: {'OK' if ok_entry else 'FAILED'}")

    # Refresh entries to get the (possibly unchanged) activity_url
    await kkn.update_logbook_entries(programs=[target_p_id], pool_size=2)
    entry = next((e for e in kkn.main_program[target_p_id]["entries"] if e.get("entry_index") == idx), None)
    if not entry:
      print(f"  [!] Could not refresh entry #{idx}, skipping sub-entries")
      continue

    if not entry.get("activity_url"):
      print(f"  [!] No activity_url available, skipping sub-entries")
      continue

    # 2. Add sub-entries
    for sub in spec["sub_entries"]:
      ok_sub = await kkn.add_logbook_sub_entry(entry["activity_url"], build_sub_payload(sub))
      print(f"  Sub-entry '{sub['title']}': {'OK' if ok_sub else 'FAILED'}")
      await asyncio.sleep(0.5)

    # Refresh after each entry group
    await kkn.update_logbook_entries(programs=[target_p_id], pool_size=2)

  await client.aclose()
  return 0


if __name__ == "__main__":
  dry = "--dry-run" in sys.argv
  sys.exit(asyncio.run(main(dry_run=dry)))
