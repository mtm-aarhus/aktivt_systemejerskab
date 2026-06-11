"""
Smoke test - bekræfter forbindelse til KITOS API V2.
Kør: python test_connection.py
"""

import sys
import requests

# Indlæs config (validerer også at miljøvariabler er sat)
from src.config import KITOS_BASE_URL, KITOS_EMAIL, KITOS_PASSWORD

AUTH_URL = "https://kitos.dk/api/authorize/GetToken"


def get_token() -> str:
    print(f"[1/3] Autentificerer som {KITOS_EMAIL} ...")
    resp = requests.post(
        AUTH_URL,
        json={"email": KITOS_EMAIL, "password": KITOS_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  FEJL: HTTP {resp.status_code}")
        print(f"  Svar: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()
    token = (
        data.get("token")
        or data.get("access_token")
        or data.get("value")
        or (data.get("response") or {}).get("token")
    )
    if not token:
        print(f"  FEJL: Ingen token i svar: {data}")
        sys.exit(1)

    print(f"  OK: Token modtaget ({token[:20]}...)")
    return token


def test_read(token: str):
    print("[2/3] Henter IT-systemer (pageSize=1) ...")
    resp = requests.get(
        f"{KITOS_BASE_URL}/it-systems",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 0, "pageSize": 1},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  FEJL: HTTP {resp.status_code}")
        print(f"  Svar: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()
    count = len(data) if isinstance(data, list) else "?"
    print(f"  OK: Modtog {count} post(er)")
    if isinstance(data, list) and data:
        first = data[0]
        print(f"  Eksempel: uuid={first.get('uuid')}, name={first.get('name')}")


def test_org(token: str):
    print("[3/3] Henter organisationer (pageSize=1) ...")
    resp = requests.get(
        f"{KITOS_BASE_URL}/organizations",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 0, "pageSize": 1},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  FEJL: HTTP {resp.status_code}")
        print(f"  Svar: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()
    count = len(data) if isinstance(data, list) else "?"
    print(f"  OK: Modtog {count} organisation(er)")
    if isinstance(data, list) and data:
        first = data[0]
        print(f"  Eksempel: uuid={first.get('uuid')}, name={first.get('name')}, cvr={first.get('cvr')}")


if __name__ == "__main__":
    print(f"=== KITOS API V2 forbindelsestest ===")
    print(f"Base URL : {KITOS_BASE_URL}")
    print(f"Bruger   : {KITOS_EMAIL}")
    print()

    token = get_token()
    test_read(token)
    test_org(token)

    print()
    print("=== ALT OK - Forbindelse bekræftet ===")
