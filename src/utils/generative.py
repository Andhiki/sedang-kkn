import os

from google import genai

from ui.tui import print_log


def is_generative_ai_available():
  if not os.getenv("GEMINI_API_KEY"):
    print_log("GEMINI_API_KEY not found in environment variables.")
    print_log("AI features will be disabled. To enable them, please set the key in your .env file.")
    return False

  return True


def generate_content(prompt: str) -> str:
  print("Calling Gemini API...")
  try:
    client = genai.Client()
    response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
    return (response.text or "").strip()
  except Exception as e:
    print_log(f"An error occurred during content generation: {e}", "ERROR")
    return "Gagal menghasilkan konten dari AI."


def generate_description_prompt(program_title: str, activity_title: str, additional_context: str | None = None) -> str:
  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Deskripsi Kegiatan' yang baik dan profesional untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"- **Judul Program Kerja (Proker) Utama:** {program_title}\n"
    f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {activity_title}\n\n"
    f"**Instruksi:**\n"
    f"1. Tulis deskripsi dalam Bahasa Indonesia yang formal dan jelas.\n"
    f"2. Deskripsi harus menjelaskan secara singkat apa yang dilakukan dalam kegiatan '{activity_title}' sebagai bagian dari program kerja '{program_title}'.\n"
    f"3. Jelaskan tujuan singkat dari kegiatan ini dan relevansinya terhadap proker utama.\n"
    f"4. Buat deskripsi minimal 300 karakter dan isian meliputi keterlibatan warga, tantangan yang dihadapi, bantuan dari pemerintah desa, kesesuaian dengan program desa"
    ", metodologi pendekatan yang dikerjakan dan tanggapan masyarakat. Jangan terlalu panjang. Jangan gunakan formatting, hanya response dengan deskripsi kegiatan.\n\n"
    f"**Contoh Output:**\n"
    f"Kegiatan ini merupakan bagian dari pelaksanaan program kerja '{program_title}'. "
    f"Fokus dari kegiatan ini adalah untuk [jelaskan tujuan singkat kegiatan]. "
    f"Hal ini dilakukan untuk mendukung pencapaian tujuan utama program kerja dalam [sebutkan relevansi dengan proker]."
    f"{f'**Konteks:**\n{additional_context}' if additional_context else ''}"
  )


def generate_result_prompt(proker_title: str, kegiatan_title: str, description: str) -> str:
  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Hasil Kegiatan' yang baik dan positif untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"- **Judul Program Kerja (Proker) Utama:** {proker_title}\n"
    f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {kegiatan_title}\n"
    f"- **Deskripsi Kegiatan yang sudah dibuat:** {description}\n\n"
    f"**Instruksi:**\n"
    f"1. Tulis hasil kegiatan dalam Bahasa Indonesia yang formal.\n"
    f"2. Tuliskan bahwa kegiatan telah dilaksanakan dengan baik dan lancar.\n"
    f"3. Sebutkan output atau hasil positif yang singkat dan jelas dari kegiatan tersebut.\n"
    f"4. Buat hasil kegiatan dalam 1-2 kalimat saja. Jangan terlalu panjang (kurang dari 255 karakter). Jangan gunakan formatting, hanya response dengan hasil kegiatan saja\n\n"
    f"**Contoh Output:**\n"
    f"Kegiatan ini telah berhasil dilaksanakan sesuai dengan rencana dan berjalan dengan lancar. "
    f"Hasil yang dicapai adalah [sebutkan hasil positif singkat], memberikan kontribusi positif terhadap program kerja."
  )
