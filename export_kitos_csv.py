"""
Eksporterer MTM (Teknik og Miljø) IT-systemanvendelser fra KITOS til CSV og TypeScript mock-data.

Kræver kun KITOS_EMAIL og KITOS_PASSWORD i .env — ingen Azure/SharePoint-adgang.

Output:
  data/kitos_mtm_export.csv   – MTM-systemer som CSV (Excel-kompatibel UTF-8)
  data/kitos_mtm_export.json  – MTM-systemer som JSON
  data/kitos_mock_data.ts     – TypeScript mock-data klar til SPFx
  [SPFx]/services/mockData.ts – Auto-kopieres til SPFx-projektet

Kør:
  python export_kitos_csv.py           (kun MTM-systemer, uden DPR-opslag — hurtigt)
  python export_kitos_csv.py --alle    (alle systemer, ikke kun MTM)
  python export_kitos_csv.py --dprs    (inkludér DPR-opslag — langsomt, én kald per system)
"""

import csv
import json
import sys
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Mapper har kun stdlib-imports — tryg at importere direkte
sys.path.insert(0, str(Path(__file__).parent))
from src.mapper import map_kitos_to_sharepoint

load_dotenv()

KITOS_EMAIL    = os.getenv("KITOS_EMAIL")
KITOS_PASSWORD = os.getenv("KITOS_PASSWORD")
KITOS_BASE_URL = os.getenv("KITOS_BASE_URL", "https://kitos.dk/api/v2")
HENT_DPRS      = "--dprs" in sys.argv
KUN_MTM        = "--alle" not in sys.argv

# Nøgleord der identificerer MTM (Teknik og Miljø) organisationsenheder
MTM_KEYWORDS = ["teknik", "milj", "mtm"]


# ── Autentifikation ───────────────────────────────────────────────────────────

def get_token() -> str:
    if not KITOS_EMAIL or not KITOS_PASSWORD:
        print("FEJL: Sæt KITOS_EMAIL og KITOS_PASSWORD i .env")
        sys.exit(1)
    resp = requests.post(
        "https://kitos.dk/api/authorize/GetToken",
        json={"email": KITOS_EMAIL, "password": KITOS_PASSWORD},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["response"]["token"]


# ── Data-hentning ─────────────────────────────────────────────────────────────

def fetch_all_systems(token: str) -> list:
    headers = {"Authorization": f"Bearer {token}"}
    systems, page = [], 0
    while True:
        resp = requests.get(
            f"{KITOS_BASE_URL}/it-system-usages",
            headers=headers,
            params={"page": page, "pageSize": 250},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        systems.extend(batch)
        print(f"  Side {page}: {len(batch)} systemer — i alt {len(systems)}")
        page += 1
    return systems


def fetch_dprs(token: str, system_usage_uuid: str) -> list:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(
            f"{KITOS_BASE_URL}/data-processing-registrations",
            headers=headers,
            params={"systemUsageUuid": system_usage_uuid, "page": 0, "pageSize": 100},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json() or []
    except Exception:
        return []


# ── TypeScript mock-fil generering ────────────────────────────────────────────

# Felter der er URL-objekter i SharePoint (skal have { Url, Description } format)
_URL_FIELDS = {"GDPRAnmeldelseURL"}


def _ts_value(v, field_name: str = "") -> str:
    if v is None:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # URL-felter skal pakkes i { Url, Description } objekt
        if field_name in _URL_FIELDS:
            escaped_url = v.replace("\\", "\\\\").replace("'", "\\'")
            return f"{{ Url: '{escaped_url}', Description: 'GDPR Anmeldelse' }}"
        escaped = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        return f"'{escaped}'"
    return f"'{str(v)}'"


def generate_ts(mapped: list, ts_path: Path) -> None:
    lines = [
        "// Auto-genereret af export_kitos_csv.py — redigér ikke manuelt",
        "// Regenerér med: python export_kitos_csv.py",
        "import { IItSystem } from './ISharePointTypes';",
        "",
        "export const MOCK_SYSTEMER: IItSystem[] = [",
    ]
    for row in mapped:
        lines.append("  {")
        for k, v in row.items():
            if v is not None:
                lines.append(f"    {k}: {_ts_value(v, k)},")
        lines.append("  },")
    lines.append("];")
    ts_path.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    print("Henter KITOS Bearer token...")
    token = get_token()

    print("\nHenter alle IT-systemanvendelser...")
    all_systems = fetch_all_systems(token)
    print(f"\nHentet {len(all_systems)} systemer i alt.")

    if KUN_MTM:
        def er_mtm(s) -> bool:
            org = (s.get("organizationUsage") or {})
            enhed = (org.get("responsibleOrganizationUnit") or {}).get("name", "").lower()
            # Tjek også alle "Relevante organisationsenheder" (usingOrganizationUnits i API)
            using = " ".join(
                u.get("name", "").lower()
                for u in (org.get("usingOrganizationUnits") or [])
            )
            return any(kw in enhed or kw in using for kw in MTM_KEYWORDS)

        systems = [s for s in all_systems if er_mtm(s)]
        print(f"Filtreret til {len(systems)} MTM-systemer (brug --alle for alle).\n")
    else:
        systems = all_systems
        print(f"Eksporterer alle {len(systems)} systemer.\n")

    if HENT_DPRS:
        print("Mapper data med DPR-opslag (kan tage et stykke tid)...")
    else:
        print("Mapper data (uden DPR-opslag — brug --dprs for databehandleraftaler)...")

    mapped = []
    for i, system in enumerate(systems, 1):
        dprs = fetch_dprs(token, system["uuid"]) if HENT_DPRS else []
        row = map_kitos_to_sharepoint(system, dprs)
        row["ID"] = i
        mapped.append(row)
        if i % 25 == 0:
            print(f"  {i}/{len(systems)} mappet...")

    prefix = "kitos_mtm" if KUN_MTM else "kitos_alle"

    # CSV
    csv_path = output_dir / f"{prefix}_export.csv"
    if mapped:
        cols = list(mapped[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(mapped)
    print(f"\nCSV gemt:  {csv_path}")

    # JSON (bruges til mock-data i SPFx)
    json_path = output_dir / f"{prefix}_export.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mapped, f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON gemt: {json_path}")

    # TypeScript mock-data
    ts_path = output_dir / "kitos_mock_data.ts"
    generate_ts(mapped, ts_path)
    print(f"TS gemt:   {ts_path}")

    # Destinationer i SPFx-projekt
    spfx_services = Path(r"C:\Users\azmda0l\Source\aktivt-systemejerskab-spfx\src\webparts\systemejerskab\services")
    spfx_ts_target   = spfx_services / "mockData.ts"
    spfx_json_target = spfx_services / "kitosData.json"

    print(f"\n{'='*60}")
    print(f"Færdigt — {len(mapped)} systemer eksporteret.")

    # Auto-kopiér til SPFx-projektet hvis det eksisterer
    if spfx_services.exists():
        import shutil
        shutil.copy(ts_path,   spfx_ts_target)
        shutil.copy(json_path, spfx_json_target)
        print(f"\nAuto-kopieret til SPFx:")
        print(f"  {spfx_ts_target}")
        print(f"  {spfx_json_target}")
        print(f"\nStart SPFx workbench med mock-data:")
        print(f"  cd C:\\Users\\azmda0l\\Source\\aktivt-systemejerskab-spfx")
        print(f"  gulp serve")
    else:
        print(f"\nManuel kopi til SPFx:")
        print(f"  Copy-Item \"{ts_path}\" \"{spfx_ts_target}\"")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
