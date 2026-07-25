#!/usr/bin/env python3
"""
AS-VISA Schengen Randevu Takip Botu
------------------------------------
appointment.as-visa.com sitesindeki randevu kotalarini kontrol eder,
uygun bir randevu bulundugunda Telegram uzerinden bildirim gonderir.

ONEMLI: Bu script randevuyu OTOMATIK ALMAZ, sadece kontrol edip haber verir.
Basvuru formunu doldurup randevuyu onaylama islemini kullanici kendisi,
bildirimi aldiktan sonra elle tamamlamalidir.
"""

import os
import sys
import json
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# AYARLAR - ihtiyacina gore duzenleyebilirsin
# --------------------------------------------------------------------------

LOCATIONS = {
    "Istanbul Piyalepasa": "https://appointment.as-visa.com/tr/basvuru-yeri/istanbul-piyalepasa",
    "Ankara Cankaya": "https://appointment.as-visa.com/tr/basvuru-yeri/ankara-cankaya",
}

NO_SLOT_TEXT = "Aktif Randevu Kotası Bulunmamaktadır"
ERROR_THRESHOLD = 5

STATE_FILE = "state.json"
REQUEST_TIMEOUT = 20

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("UYARI: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanimli degil.")
        print(f"Gonderilecek mesaj:\n{text}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Telegram mesaji gonderilemedi: {e}")
        return False


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_location(name: str, url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"name": name, "url": url, "available": None, "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    available = NO_SLOT_TEXT not in page_text
    return {"name": name, "url": url, "available": available, "error": None}


def run_test_message():
    ok = send_telegram_message(
        "\u2705 Test mesaji: Schengen randevu botu dogru kuruldu ve "
        "Telegram'a baglanabiliyor. Randevu acildiginda buradan haber "
        "alacaksin."
    )
    sys.exit(0 if ok else 1)


def main():
    state = load_state()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Kontrol basliyor...")

    for name, url in LOCATIONS.items():
        loc_state = state.get(name, {})
        result = check_location(name, url)

        if result["error"]:
            error_count = loc_state.get("error_count", 0) + 1
            print(f"  - {name}: HATA ({error_count}. kez) -> {result['error']}")

            if error_count == ERROR_THRESHOLD and not loc_state.get("error_warned"):
                send_telegram_message(
                    f"\u26a0\ufe0f <b>{name}</b> kontrol edilirken art arda "
                    f"{ERROR_THRESHOLD} kez hata alindi. Site yapisi degismis "
                    f"ya da erisim engellenmis olabilir, botu kontrol etmen "
                    f"gerekebilir.\nSon hata: {result['error']}"
                )
                loc_state["error_warned"] = True

            loc_state["error_count"] = error_count
            state[name] = loc_state
            continue

        prev_available = loc_state.get("available", False)
        status_text = "UYGUN RANDEVU VAR" if result["available"] else "randevu yok"
        print(f"  - {name}: {status_text}")

        if result["available"] and not prev_available:
            send_telegram_message(
                f"\U0001f6a8 <b>Randevu firsati olabilir!</b>\n\n"
                f"\U0001f4cd {name}\n"
                f"\U0001f517 {url}\n\n"
                f"Kontenjanlar hizli dolabiliyor, hemen kontrol et."
            )

        state[name] = {
            "available": result["available"],
            "checked_at": now,
            "error_count": 0,
            "error_warned": False,
        }

    save_state(state)
    print(f"[{now}] Kontrol tamamlandi.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test_message()
    else:
        main()
