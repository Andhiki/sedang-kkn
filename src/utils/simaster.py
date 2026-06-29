import asyncio
import hashlib
import os
import re
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from cachelib import FileSystemCache

from ui.tui import console, print_log
from utils.logger import get_logger

log = get_logger("simaster")

BASE_URL = "https://simaster.ugm.ac.id"
HOME_URL = f"{BASE_URL}/beranda"
LOGIN_URL = f"{BASE_URL}/services/simaster/service_login"
SSO_BASE_URL = "https://sso.ugm.ac.id"
SSO_LOGIN_URL = f"{SSO_BASE_URL}/cas/login"
SIGNIN_URL = f"{BASE_URL}/ugmfw/signin_simaster/signin_proses"
CAPTCHA_VERIFY_URL = f"{BASE_URL}/ugmfw/signin_simaster/captchasound_verification"
CAPTCHA_IMAGE_URL = f"{BASE_URL}/ugmfw/signin_simaster/captcha_sound/"
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CACHE_THRESHOLD = int(os.getenv("CACHE_THRESHOLD", str(500)))

SSO_TIMEOUT = float(os.getenv("SSO_TIMEOUT", "30"))
SSO_MAX_RETRIES = int(os.getenv("SSO_MAX_RETRIES", "3"))
SSO_RETRY_BACKOFF = float(os.getenv("SSO_RETRY_BACKOFF", "2.0"))

SSO_USER_AGENT = (
  "Mozilla/5.0 (Linux; Android 12; sdk_gphone64_x86_64 Build/SE1A.220826.008; wv) "
  "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36"
)

MAX_CAPTCHA_ATTEMPTS = 5

TRANSIENT_EXCEPTIONS = (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)


def _solve_captcha(image_bytes: bytes) -> str | None:
  try:
    import ddddocr

    ocr = ddddocr.DdddOcr(show_ad=False)
    result = ocr.classification(image_bytes)
    if result:
      log.info("Captcha solved: %s", result)
      return result
  except Exception as e:
    log.error("Captcha OCR failed: %s", e)
  return None


class Simaster:
  def __init__(self, username: str, password: str):
    self.username = username
    self.password = password
    self.last_login_transient = False
    try:
      CACHE_DIR.mkdir(parents=True, exist_ok=True)
      self.cache: FileSystemCache = FileSystemCache(str(CACHE_DIR), threshold=CACHE_THRESHOLD)
    except OSError:
      from cachelib import SimpleCache

      self.cache = SimpleCache()

  def _get_cache_key(self, username: str, password: str):
    return hashlib.md5(f"{username}:{password}".encode()).hexdigest()

  async def _check_cache(self, key: str) -> httpx.AsyncClient | None:
    if not (cookies := self.cache.get(key)):
      return None

    client = httpx.AsyncClient(cookies=cookies, timeout=5.0)

    try:
      resp = await client.get(HOME_URL, follow_redirects=True)
      if resp.status_code == 200:
        print("Cached session is valid.")
        return client
      else:
        print("Cached session is invalid or expired.")
        await client.aclose()
    except httpx.RequestError as e:
      print(f"Failed to validate cached session: {e}")
      await client.aclose()

    return None

  async def _solve_captcha_and_verify(self, client: httpx.AsyncClient, captcha_page_html: str) -> bool:
    token_match = re.search(r'name="simasterUGM_token"[^>]*value="([^"]+)"', captcha_page_html)
    if not token_match:
      log.error("Captcha page: could not extract simasterUGM_token")
      return False
    simaster_token = token_match.group(1)

    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
      log.info("Captcha attempt %d/%d for %s", attempt, MAX_CAPTCHA_ATTEMPTS, self.username)

      captcha_url = f"{CAPTCHA_IMAGE_URL}?_={hashlib.md5(str(os.urandom(16)).encode()).hexdigest()}"
      img_resp = await client.get(captcha_url)
      if img_resp.status_code != 200:
        log.error("Failed to download captcha image (status %d)", img_resp.status_code)
        return False

      captcha_text = _solve_captcha(img_resp.content)
      if not captcha_text:
        log.error("Captcha OCR returned empty result")
        return False

      data = {
        "simasterUGM_token": simaster_token,
        "captcha": captcha_text,
      }
      headers = {
        "User-Agent": SSO_USER_AGENT,
        "Referer": CAPTCHA_VERIFY_URL,
        "Content-Type": "application/x-www-form-urlencoded",
      }
      verify_resp = await client.post(CAPTCHA_VERIFY_URL, data=data, headers=headers, follow_redirects=True)
      final_url = str(verify_resp.url)

      if "captcha" in final_url.lower():
        log.warning("Captcha verification failed (attempt %d), retrying with new captcha", attempt)
        captcha_page_html = verify_resp.text
        token_match = re.search(r'name="simasterUGM_token"[^>]*value="([^"]+)"', captcha_page_html)
        if token_match:
          simaster_token = token_match.group(1)
        continue

      if "login" in final_url.lower() or "signin" in final_url.lower():
        log.error("Captcha verification redirected back to login — session lost")
        return False

      log.info("Captcha verification successful for %s", self.username)
      return True

    log.error("Captcha verification failed after %d attempts for %s", MAX_CAPTCHA_ATTEMPTS, self.username)
    return False

  async def _sso_login_attempt(self, verbose: bool = False) -> httpx.AsyncClient | None:
    client = httpx.AsyncClient(timeout=SSO_TIMEOUT)

    try:
      if verbose:
        print_log(f"[#89dceb]{self.username}[/]: service_login failed, trying SSO fallback...", "WARN")

      log.info("SSO fallback login for %s", self.username)

      resp = await client.get(SIGNIN_URL, follow_redirects=False)
      if resp.status_code not in (301, 302, 303, 307):
        log.error("SSO fallback: unexpected status %d from signin_proses", resp.status_code)
        await client.aclose()
        return None

      sso_url = resp.headers.get("location", "")
      if not sso_url:
        log.error("SSO fallback: no redirect from signin_proses")
        await client.aclose()
        return None

      resp = await client.get(sso_url, follow_redirects=True)
      if resp.status_code != 200:
        log.error("SSO fallback: failed to load SSO login page (status %d)", resp.status_code)
        await client.aclose()
        return None

      jsessionid = client.cookies.get("JSESSIONID", "")
      lt_match = re.search(r'name="lt"\s+value="([^"]+)"', resp.text)
      lt_token = lt_match.group(1) if lt_match else None
      if not lt_token:
        log.error("SSO fallback: could not extract lt token from SSO page")
        await client.aclose()
        return None

      parsed = urlparse(sso_url)
      service_param = parse_qs(parsed.query).get("service", [None])[0]

      login_url = f"{SSO_BASE_URL}/cas/login;jsessionid={jsessionid}"
      data = {
        "username": self.username,
        "password": self.password,
        "lt": lt_token,
        "_eventId": "submit",
        "submit": "LOGIN",
      }
      if service_param:
        data["service"] = service_param

      headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": SSO_USER_AGENT,
        "Origin": SSO_BASE_URL,
        "Referer": sso_url,
      }

      resp = await client.post(login_url, data=data, headers=headers, follow_redirects=False)
      if resp.status_code != 302:
        log.error("SSO fallback: SSO login rejected (status %d)", resp.status_code)
        await client.aclose()
        return None

      ticket_url = resp.headers.get("location", "")
      if not ticket_url:
        log.error("SSO fallback: no redirect after SSO login")
        await client.aclose()
        return None

      captcha_page_html = None
      for _ in range(10):
        next_url = resp.headers.get("location", "")
        if not next_url:
          break
        if not next_url.startswith("http"):
          next_url = f"{BASE_URL}{next_url}"

        resp = await client.get(next_url, follow_redirects=False)
        final_url = str(resp.url)

        if "/captchasound_verification" in final_url:
          captcha_page_html = resp.text
          log.info("SSO fallback: captcha verification required for %s", self.username)
          if not await self._solve_captcha_and_verify(client, captcha_page_html):
            log.error("SSO fallback: captcha verification failed for %s", self.username)
            await client.aclose()
            return None
          break

        if resp.status_code not in (301, 302, 303, 307):
          break

      beranda_resp = await client.get(HOME_URL, follow_redirects=True)
      beranda_url = str(beranda_resp.url)
      if beranda_resp.status_code != 200 or "notfound" in beranda_url.lower() or "login" in beranda_url.lower():
        log.error("SSO fallback: session not valid after login (beranda status=%d, url=%s)", beranda_resp.status_code, beranda_url[:80])
        await client.aclose()
        return None

      if verbose:
        console.print(f"[green]SSO fallback login successful for {self.username}[/]")

      log.info("SSO fallback login successful for %s", self.username)
      client.timeout = httpx.Timeout(5.0)
      self.cache.set(
        self._get_cache_key(self.username, self.password),
        dict(client.cookies),
        timeout=60 * 60 * 24 * 2,
      )
      return client

    except Exception as e:
      log.error("SSO fallback failed for %s: %s", self.username, e, exc_info=True)
      try:
        await client.aclose()
      except Exception:
        pass
      if isinstance(e, TRANSIENT_EXCEPTIONS):
        raise
      return None

  async def _sso_login(self, verbose: bool = False) -> httpx.AsyncClient | None:
    self._sso_was_transient = False
    last_exc: Exception | None = None
    for attempt in range(1, SSO_MAX_RETRIES + 1):
      try:
        result = await self._sso_login_attempt(verbose=verbose)
        if result is not None:
          if attempt > 1:
            log.info("SSO fallback succeeded on attempt %d/%d for %s", attempt, SSO_MAX_RETRIES, self.username)
          return result
        return None
      except TRANSIENT_EXCEPTIONS as e:
        last_exc = e
        if attempt < SSO_MAX_RETRIES:
          delay = SSO_RETRY_BACKOFF ** attempt
          log.warning(
            "SSO fallback attempt %d/%d transient error for %s: %s — retrying in %.1fs",
            attempt, SSO_MAX_RETRIES, self.username, e, delay,
          )
          await asyncio.sleep(delay)
        else:
          log.error(
            "SSO fallback failed after %d attempts for %s (last error: %s)",
            SSO_MAX_RETRIES, self.username, e,
          )
    self._sso_was_transient = True
    return None

  async def login(
    self,
    username: str | None = None,
    password: str | None = None,
    reuse_session: bool = True,
    verbose: bool = False,
  ) -> httpx.AsyncClient | None:
    self.username = username or self.username
    self.password = password or self.password
    self.last_login_transient = False

    key = self._get_cache_key(self.username, self.password)
    if reuse_session and (client := await self._check_cache(key)):
      return client

    client = httpx.AsyncClient(timeout=5.0)
    login_data = {"aId": "", "username": self.username, "password": self.password}

    try:
      status_context = (
        console.status(f"[bold green]Logging in as [bold #89dceb]{self.username}[/]...", spinner="dots")
        if verbose
        else nullcontext()
      )

      with status_context:
        resp = await client.post(LOGIN_URL, data=login_data, follow_redirects=True)
        resp.raise_for_status()
        resp_json = resp.json()

      if resp_json.get("isLogin") == 1:
        if verbose:
          console.print(f"[green]Succesfully logged in as {resp_json.get('namaLengkap')}[/]")

        self.cache.set(key, dict(client.cookies), timeout=60 * 60 * 24 * 2)
        return client
      else:
        if verbose:
          print_log("Login failed, Please check your username and password.", "ERROR")

        await client.aclose()

        log.info("service_login returned isLogin=0 for %s, trying SSO fallback", self.username)
        result = await self._sso_login(verbose=verbose)
        if result is None:
          self.last_login_transient = self._sso_was_transient
        return result

    except TRANSIENT_EXCEPTIONS as e:
      if verbose:
        print_log(f"Network error during login for {self.username}: {e}", "ERROR")

      log.warning("service_login raised transient %s for %s, trying SSO fallback", type(e).__name__, self.username)
      await client.aclose()
      result = await self._sso_login(verbose=verbose)
      if result is None:
        self.last_login_transient = True
      return result

    except Exception as e:
      if verbose:
        print_log(f"An error occured during login: {e}", "ERROR")

      log.warning("service_login raised %s for %s, trying SSO fallback", type(e).__name__, self.username)
      await client.aclose()
      result = await self._sso_login(verbose=verbose)
      if result is None:
        self.last_login_transient = self._sso_was_transient
      return result