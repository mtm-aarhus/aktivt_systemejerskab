# Udviklingsplan: KITOS → SharePoint

## Oversigt

Formålet er at trække data ud fra KITOS API V2 og gemme det i en SharePoint-liste via Microsoft Graph API.

---

## Fase 1 — Opsætning og autentifikation

**Opgaver:**
- Konfigurer KITOS API-adgang (token/credentials i `.env`)
- Konfigurer Microsoft Graph API adgang til SharePoint (Azure App Registration med `Sites.ReadWrite.All`)
- Tilføj nødvendige biblioteker til `requirements/base.txt`

**Biblioteker:**
- `requests` — KITOS API kald
- `msal` — Microsoft Graph autentifikation
- `python-dotenv` — miljøvariabler

---

## Fase 2 — KITOS dataudtræk

**Opgaver:**
- Opret `kitos_client.py` — wrapper til KITOS API V2
- Implementer paginering (`page` + `pageSize`, maks 250 pr. kald)
- Hent IT-Systemer fra `/api/v2/it-systems` (stamdata)
- Hent IT-Systemer i organisationen via `/api/v2/it-system-usages`
- Implementer **delta-feed** med `changedSinceGtEq` timestamp så kun ændringer hentes ved gentagende kørsler
- Gem `lastSync` timestamp i en lokal fil

**Nøglepunkter fra KITOS API V2:**
- Brug UUID som nøgle (ikke id-feltet fra v1)
- Løs krydsreferencer (`exposedBySystem.uuid` → separat GET-kald)
- Læsemodel returnerer komplekse typer (`systemContext.name`, `systemContext.uuid`)
- Delta-feed endpoint: `/api/v2/delta-feed/deleted-entities` for slettede registreringer

**Eksempel på pagineret kald:**
```
GET https://kitos.dk/api/v2/it-systems?page=0&pageSize=250
```

**Eksempel på delta-feed:**
```
GET https://kitos.dk/api/v2/it-system-usages?changedSinceGtEq=2024-01-01T00:00:00.000Z&page=0&pageSize=250
```

---

## Fase 3 — SharePoint integration

**Opgaver:**
- Opret `sharepoint_client.py` — wrapper til Microsoft Graph API
- Map KITOS-felter til SharePoint-listekolonner
- Implementer upsert-logik: opret ny hvis UUID ikke findes, opdater hvis den eksisterer
- Håndter slettede registreringer via delta-feed og slet/deaktiver tilsvarende rækker i SharePoint

**Feltmapping KITOS → SharePoint:**

| KITOS felt | SharePoint kolonne | Type |
|---|---|---|
| `uuid` | `KitosUUID` (nøgle) | Tekst |
| `name` | `Title` | Tekst |
| `general.localId` | `LokalID` | Tekst |
| `organizationContext.name` | `Organisation` | Tekst |
| `lastModified` | `SidstOpdateret` | Dato |
| `deactivated` | `Deaktiveret` | Ja/Nej |

---

## Fase 4 — Orkestrering og fejlhåndtering

**Opgaver:**
- Opret `main.py` som entry point
- Logging til fil og konsol
- Retry-logik ved HTTP-fejl (429 rate limit, 5xx serverfejl)
- Gem `lastSync` timestamp **kun ved succes**
- Rapportering: antal oprettede, opdaterede og slettede poster

---

## Projektstruktur

```
Aktivtsystem_ejerskab/
├── .env                         # Miljøvariabler (ikke i git)
├── UDVIKLINGSPLAN.md
├── requirements/
│   ├── base.txt                 # requests, msal, python-dotenv
│   ├── dev.txt                  # + pytest, ruff, black
│   └── prod.txt
├── src/
│   ├── kitos_client.py          # KITOS API V2 wrapper
│   ├── sharepoint_client.py     # Microsoft Graph API wrapper
│   ├── mapper.py                # Feltmapping KITOS → SharePoint
│   └── main.py                  # Entry point / orkestrering
├── data/
│   └── sync_state.json          # Gemmer lastSync timestamp
└── logs/
    └── sync.log                 # Kørselslogs
```

---

## .env variabler der skal tilføjes

```env
# KITOS
KITOS_BASE_URL=https://kitos.dk/api/v2
KITOS_TOKEN=

# Microsoft Graph / SharePoint
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
SHAREPOINT_SITE_ID=
SHAREPOINT_LIST_ID=
```

---

## Åbne spørgsmål

- [ ] Hvilke KITOS moduler skal synkroniseres? (IT-Systemer, Kontrakter, Databehandling?)
- [ ] Hvordan autentificeres mod KITOS? (Token, API-nøgle eller brugernavn/adgangskode?)
- [ ] Eksisterer SharePoint-listen allerede, eller skal den oprettes via koden?
- [ ] Skal kørslen være et engangs-udtræk eller et planlagt job (fx dagligt)?