"""
Exploratorisk API-kald — undersøger hvad KITOS returnerer for
databehandlingsregistreringer og kontrakter.
Kør: python test_kitos_explore.py
"""

import json
import sys
import requests
from src.config import KITOS_BASE_URL, KITOS_EMAIL, KITOS_PASSWORD

AUTH_URL = "https://kitos.dk/api/authorize/GetToken"


def get_token():
    resp = requests.post(AUTH_URL, json={"email": KITOS_EMAIL, "password": KITOS_PASSWORD}, timeout=15)
    resp.raise_for_status()
    return resp.json()["response"]["token"]


def fetch(token, path, params=None):
    resp = requests.get(
        f"{KITOS_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {"page": 0, "pageSize": 1},
        timeout=15,
    )
    print(f"\n{'='*60}")
    print(f"GET {path}  ->  HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            print(json.dumps(data[0] if isinstance(data, list) else data, indent=2, ensure_ascii=False)[:2000])
        else:
            print("  (tomt svar)")
    else:
        print(f"  Fejl: {resp.text[:300]}")
    return resp


if __name__ == "__main__":
    print("Henter token...")
    token = get_token()
    print("Token OK")

    # 1. Hent eet system-usage og noter UUID
    r = fetch(token, "/it-system-usages")
    usage = r.json()[0] if r.status_code == 200 and r.json() else None
    usage_uuid = usage["uuid"] if usage else None
    print(f"\nBruger system-usage UUID: {usage_uuid}")

    # 2. DPR filter — afproev parameter med et UUID der KENDES at have DPR
    known_dpr_system_uuid = "2d06857e-2607-4377-9882-f1a142399672"  # OS2Display fra DPR-svaret
    r2 = fetch(token, "/data-processing-registrations",
               {"systemUsageUuid": known_dpr_system_uuid, "page": 0, "pageSize": 5})
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"  Antal DPR'er fundet: {len(data2)}")
        if data2:
            print(f"  isAgreementConcluded: {data2[0].get('general', {}).get('isAgreementConcluded')}")

    # 3. Vis roller paa system-usagen
    if usage:
        print("\n=== ROLLER paa systemet ===")
        for role in usage.get("roles", []):
            print(f"  Rolle: {role['role']['name']:30s}  Person: {role['user']['name']}")

    # 4. Fuldt it-system-usages svar (alle felter)
    if usage:
        print("\n=== ALLE FELTER paa it-system-usage ===")
        print(json.dumps(usage, indent=2, ensure_ascii=False))
