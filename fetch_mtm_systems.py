import requests
from src.config import KITOS_BASE_URL, KITOS_EMAIL, KITOS_PASSWORD

token = requests.post(
    "https://kitos.dk/api/authorize/GetToken",
    json={"email": KITOS_EMAIL, "password": KITOS_PASSWORD},
    timeout=15,
).json()["response"]["token"]

headers = {"Authorization": f"Bearer {token}"}
systems = []
page = 0
while True:
    resp = requests.get(
        f"{KITOS_BASE_URL}/it-system-usages",
        headers=headers,
        params={"page": page, "pageSize": 100},
        timeout=30,
    )
    batch = resp.json()
    if not batch:
        break
    systems.extend(batch)
    print(f"  Side {page}: {len(batch)} systemer hentet...")
    page += 1
def forvalter(s):
    return (s.get("organizationUsage") or {}).get("responsibleOrganizationUnit") or {}

def er_mtm(s):
    org = (s.get("organizationUsage") or {})
    enhed = (org.get("responsibleOrganizationUnit") or {}).get("name", "").lower()
    # Tjek også "Relevante organisationsenheder" (usingOrganizationUnits i API)
    using = " ".join(
        u.get("name", "").lower()
        for u in (org.get("usingOrganizationUnits") or [])
    )
    return any(kw in enhed or kw in using for kw in ["teknik", "milj", "mtm"])

mtm = [s for s in systems if er_mtm(s)]
print(f"\nMTM-systemer: {len(mtm)}")
for s in mtm[:10]:
    print(f"  {s['uuid']}  {s.get('systemContext', {}).get('name', '')}  [{forvalter(s).get('name', '')}]")
