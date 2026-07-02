import os
from typing import Literal

from ui.tui import print_log
from utils.logger import get_logger

log = get_logger("generative")

type AIProvider = Literal["ollama", "gemini"]


def is_generative_ai_available() -> bool:
  provider = os.getenv("AI_PROVIDER", "gemini").lower()
  if provider == "ollama":
    if not os.getenv("OLLAMA_BASE_URL"):
      print_log("OLLAMA_BASE_URL not found in environment variables.")
      print_log("AI features will be disabled. Set it in your .env file to enable Ollama Cloud.")
      return False
    return True

  if not os.getenv("GEMINI_API_KEY"):
    print_log("GEMINI_API_KEY not found in environment variables.")
    print_log("AI features will be disabled. Set AI_PROVIDER=ollama or GEMINI_API_KEY in your .env file.")
    return False

  return True


def generate_content(prompt: str) -> str:
  provider = os.getenv("AI_PROVIDER", "gemini").lower()
  print(f"Calling {provider} API...")
  try:
    if provider == "ollama":
      return _generate_via_ollama(prompt)
    return _generate_via_gemini(prompt)
  except Exception as e:
    print_log(f"An error occurred during content generation: {e}", "ERROR")
    log.error("Content generation failed (%s): %s", provider, e, exc_info=True)
    return "Gagal menghasilkan konten dari AI."


def _generate_via_ollama(prompt: str) -> str:
  import httpx

  base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com").rstrip("/")
  api_key = os.getenv("OLLAMA_API_KEY")
  model = os.getenv("OLLAMA_MODEL", "qwen3.5:397b")

  url = f"{base_url}/v1/chat/completions"
  headers = {"Content-Type": "application/json"}
  if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

  payload = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
  }

  with httpx.Client(timeout=60.0, follow_redirects=True) as client:
    resp = client.post(url, json=payload, headers=headers)
    if resp.status_code == 301:
      raise RuntimeError(f"Ollama base URL returned redirect. Check OLLAMA_BASE_URL in .env. Current: {base_url or '(empty)'}. For local Ollama use http://localhost:11434")
    resp.raise_for_status()
    data = resp.json()

  choices = data.get("choices", [])
  if choices:
    content = choices[0].get("message", {}).get("content", "")
  else:
    content = data.get("message", {}).get("content", "")

  return (content or "").strip()


def _generate_via_gemini(prompt: str) -> str:
  from google import genai

  client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
  model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
  response = client.models.generate_content(model=model, contents=prompt)
  return (response.text or "").strip()


def generate_description_prompt(
  program_title: str,
  activity_title: str,
  additional_context: str | None = None,
  entry_title: str | None = None,
) -> str:
  context_lines = f"- **Judul Program Kerja (Proker) Utama:** {program_title}\n"
  if entry_title:
    context_lines += f"- **Judul Tahapan (Entry):** {entry_title}\n"
  context_lines += f"- **Judul Sub-Tahapan (Sub-Kegiatan yang sedang diisi):** {activity_title}\n"

  focus = (
    f"3. **Fokus utama adalah sub-tahapan '{activity_title}'.** "
    f"Tuliskan deskripsi yang spesifik menjelaskan apa yang dilakukan dalam sub-tahapan ini, "
    f"bukan deskripsi umum tentang proker atau tahapan. "
    f"Gunakan judul sub-tahapan sebagai panduan isi kegiatan.\n"
  ) if activity_title else ""

  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Deskripsi Kegiatan' yang baik dan profesional untuk sub-tahapan logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"{context_lines}\n"
    f"**Instruksi:**\n"
    f"1. Tulis deskripsi dalam Bahasa Indonesia yang formal dan jelas.\n"
    f"2. Deskripsi harus spesifik menjelaskan apa yang dilakukan dalam sub-tahapan "
    f"'{activity_title}' sebagai bagian dari tahapan "
    f"{f"'{entry_title}' " if entry_title else ""}dalam program kerja '{program_title}'.\n"
    f"{focus}"
    f"4. Panjang deskripsi 300-500 karakter. Jangan kurang dari 300, jangan lebih dari 500. "
    f"Isian dapat meliputi keterlibatan warga, tantangan yang dihadapi, bantuan dari pemerintah desa, "
    f"kesesuaian dengan program desa, metodologi pendekatan, dan tanggapan masyarakat bila relevan. "
    f"Jangan gunakan formatting, hanya respons dengan deskripsi kegiatan.\n\n"
    f"**Contoh Output:**\n"
    f"Kegiatan '{activity_title}' dilaksanakan sebagai bagian dari "
    f"{f"tahapan '{entry_title}' dalam " if entry_title else ""}program kerja '{program_title}'. "
    f"Fokus dari sub-tahapan ini adalah untuk [jelaskan tujuan spesifik berdasarkan judul sub-tahapan]. "
    f"Metodologi yang digunakan adalah [jelaskan pendekatan singkat]. "
    f"Kegiatan ini mendapat respons positif dari [sebutkan pihak terkait bila relevan]."
    f"{f'\n\n**Konteks Tambahan:**\n{additional_context}' if additional_context else ''}"
  )


def generate_result_prompt(
  proker_title: str,
  kegiatan_title: str,
  description: str,
  entry_title: str | None = None,
) -> str:
  context_lines = f"- **Judul Program Kerja (Proker) Utama:** {proker_title}\n"
  if entry_title:
    context_lines += f"- **Judul Tahapan (Entry):** {entry_title}\n"
  context_lines += f"- **Judul Sub-Tahapan (Sub-Kegiatan):** {kegiatan_title}\n"

  return (
    f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
    f"Buatkan 'Hasil Kegiatan' yang baik dan positif untuk sub-tahapan logbook KKN.\n\n"
    f"**Informasi Konteks:**\n"
    f"{context_lines}"
    f"- **Deskripsi Kegiatan yang sudah dibuat:** {description}\n\n"
    f"**Instruksi:**\n"
    f"1. Tulis hasil kegiatan dalam Bahasa Indonesia yang formal.\n"
    f"2. Tuliskan bahwa kegiatan telah dilaksanakan dengan baik dan lancar.\n"
    f"3. **Hasil harus spesifik terkait sub-tahapan '{kegiatan_title}'** — sebutkan output konkret "
    f"yang relevan dengan judul sub-tahapan, bukan hasil generik.\n"
    f"4. Buat hasil kegiatan dalam 1-2 kalimat saja. Maksimal 200 karakter. "
    f"Jangan gunakan formatting, hanya respons dengan hasil kegiatan saja.\n\n"
    f"**Contoh Output:**\n"
    f"Sub-tahapan '{kegiatan_title}' telah berhasil dilaksanakan dengan lancar. "
    f"Hasil yang dicapai adalah [sebutkan hasil konkret spesifik sesuai judul sub-tahapan], "
    f"memberikan kontribusi positif terhadap {f"tahapan '{entry_title}' dan " if entry_title else ""}program kerja '{proker_title}'."
  )


def generate_report_narrative_prompt(summary_data: str) -> str:
  return (
    "Anda adalah seorang mahasiswa KKN UGM yang membuat laporan mingguan.\n"
    "Berdasarkan data kehadiran dan kegiatan KKN berikut, buatlah narasi ringkas "
    "(maksimal 3 paragraf) dalam Bahasa Indonesia yang formal.\n\n"
    "Narasi harus mencakup: ringkasan kehadiran, kegiatan utama yang dilakukan, "
    "dan rencana singkat untuk periode berikutnya. Jangan gunakan formatting markdown, "
    "hanya teks biasa.\n\n"
    f"**Data Kehadiran & Kegiatan:**\n{summary_data}"
  )
