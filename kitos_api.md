# KITOS API Design (V2)

## Introduktion

Arbejdet med version 2 af KITOS API blev igangsat i foråret 2021 og udvikles i seks etaper:

### Etape 1: IT-Systemer (i kataloget) og Snitflader
- KITOSUDV-63: Rettighedshaver og interessent API til It-System katalog og snitfladekatalog (LEVERET)

### Etape 2: IT-Systemer i kommunen
- KITOSUDV-1928: Som kommunebruger vil jeg med API-adgang kunne administrere mine IT-systemer i min kommune (LEVERET)

### Etape 3: Databehandling
- KITOSUDV-1949: Som kommunebruger vil jeg med API-adgang kunne administrere mine registreringer under modulet Databehandling (LEVERET)

### Etape 4: Kontrakter
- KITOSUDV-1950: Som API-bruger vil jeg kunne administrere kontrakterne i min kommune (LEVERET)

### Etape 5: Delta Feed
- KITOSUDV-2041: Som API-bruger vil jeg kun hente ændringer siden sidste udtræk (LEVERET)

### Etape 6: PATCH i høj opløsning
- KITOSUDV-2358: PATCH på API V2 (LEVERET)

Formålet med arbejdet er at stille et funktionelt og komplet API til rådighed, hvor interessenter, rettighedshavere, leverandører og kommuner kan læse og skrive data til og fra KITOS samtidig med, at forretningsreglerne overholdes.

Version 2 er skrevet fra bunden og udviklet i tæt samarbejde med de anvendende interessenter.

## Udfases version 1?

Ja. Version 1 er udfaset og ikke længere tilgængelig med JWT.

---

# Designbeslutninger

API'et udvikles med afsæt i de logiske grupperinger (moduler/rodaggregater), der eksisterer i KITOS.

Følgende HTTP-verber understøttes:

| Metode | Beskrivelse |
|----------|------------|
| POST | Opret ny ressource |
| GET | Hent eksisterende ressource |
| PUT | Erstat eksisterende ressource |
| PATCH | Delvis opdatering af ressource |
| DELETE | Nedlæg ressource |

Grundlæggende gives der adgang til de samme data som i KITOS UI.

---

## UUID'er

Alle ressourcer tildeles en stabil og unik UUID.

I Version 1 blev det interne databasefelt `Id` ofte anvendt som identifikation. Dette erstattes i Version 2 af UUID som eneste gyldige identifikator.

---

## Paginering på listeudtræk

Listeendpoints understøtter følgende parametre:

| Parameter | Beskrivelse |
|------------|-------------|
| pageSize | Antal resultater pr. side |
| page | Sideoffset |

Eksempel:

```http
GET https://kitos.dk/api/v2/it-systems?page=0&pageSize=50
```

Hvis parametrene udelades, anvendes standardværdierne fra Swagger-dokumentationen.

---

## Centreret omkring rodaggregater

KITOS API er opbygget omkring følgende rodaggregater:

- IT-Systemer fra kataloget (stamdata)
- IT-Systemer i organisationen
- Snitflader
- Kontrakter
- Databehandling

Derudover findes understøttende API'er til:

- Udfaldsrum
- Organisationer
- Brugere i organisationen

Målet er at kunne læse og skrive alle relevante data inden for rodaggregaterne.

---

# Delta-feed

## Ændrede registreringer

Det er muligt at hente registreringer ændret siden et bestemt UTC-tidspunkt.

Eksempel:

```http
GET https://kitos.dk/api/v2/data-processing-registrations
    ?changedSinceGtEq=2021-09-27T11:50:00.021Z
    &page=0
    &pageSize=100
```

Resultaterne sorteres stigende efter `LastModified`.

---

## Slettede registreringer

Der findes et særskilt endpoint til slettede registreringer.

Eksempel:

```http
GET https://kitos.dk/api/v2/delta-feed/deleted-entities
    ?entityType=DataProcessingRegistration
    &deletedSinceUTC=2021-09-27T11:50:00.153Z
    &page=0
    &pageSize=100
```

---

# Krydsreferencer

Når en ressource refererer til en anden ressource, returneres en krydsreference.

Eksempel:

```json
{
  "exposedBySystem": {
    "name": "test",
    "uuid": "ccb5a066-3e14-489a-a9d4-91193e12d53d"
  }
}
```

Yderligere oplysninger kan hentes via:

```http
GET https://kitos.dk/api/v2/it-systems/ccb5a066-3e14-489a-a9d4-91193e12d53d
```

---

# Særskilte læse- og skrivemodeller

Læsning og skrivning benytter ikke nødvendigvis samme datamodel.

## Krydsreferencer

### Læsemodel

```json
{
  "systemContext": {
    "uuid": "00000000-0000-0000-0000-000000000000",
    "name": "string"
  },
  "organizationContext": {
    "cvr": "string",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "name": "string"
  }
}
```

### Skrivemodel

```json
{
  "systemUuid": "00000000-0000-0000-0000-000000000000",
  "organizationUuid": "00000000-0000-0000-0000-000000000000"
}
```

---

## Beregnede statusfelter

Beregnede statusfelter eksponeres kun på læsemodeller.

Eksempler:

- Kontraktstatus
- Systemstatus
- Databehandlingsstatus

Status beregnes automatisk på baggrund af øvrige registreringer.

---

## Loginformationer

Følgende oplysninger findes kun på læsemodeller:

- CreatedBy
- LastModified
- Øvrige logoplysninger

---

# Informationen findes der hvor den registreres

KITOS API følger princippet om én autoritativ datakilde.

Eksempler:

### Udstillede snitflader

Vises flere steder i UI, men registreres på stamdata.

### Systemhierarki

Registreres på stamdata via:

```text
ParentSystem
```

Data skal derfor hentes fra stamdata-API'et.

---

# Opdateringer

Version 2 understøtter:

- Oprettelse
- Opdatering
- Nedlæggelse

af ressourcer.

---

## Obligatoriske og valgfrie felter

Swagger markerer:

- Obligatoriske felter
- Valgfrie felter (`optional`)

Regler:

- Obligatoriske felter SKAL sendes ved POST og PUT.
- Valgfrie felter MÅ sendes.
- Udeladte valgfrie felter nulstilles ved PUT og POST.

---

# PUT

PUT erstatter hele ressourcen.

Anbefalet fremgangsmåde:

1. Hent eksisterende ressource

```http
GET /api/v2/{resource-type}/{uuid}
```

2. Flet eksisterende data med ændringer

3. Gem resultatet

```http
PUT /api/v2/{resource-type}/{uuid}
```

---

# PATCH

PATCH anvendes til delvise opdateringer.

KITOS understøtter:

> RFC 7396 - JSON Merge Patch

---

## Udgangspunkt

```json
{
  "name": "a name",
  "general": {
    "enabled": false,
    "localId": "a local id"
  },
  "parentUuid": "CF397900-4550-4E6C-A2AC-C329BBBB7475"
}
```

---

## Scenario 1 - Opdater navn

```http
PATCH /api/v2/{resource}/{uuid}
```

```json
{
  "name": "a new name"
}
```

---

## Scenario 2 - Opdater localId

```http
PATCH /api/v2/{resource}/{uuid}
```

```json
{
  "general": {
    "localId": "a new local id"
  }
}
```

---

## Scenario 3 - Opdater navn og parentUuid

```http
PATCH /api/v2/{resource}/{uuid}
```

```json
{
  "name": "a new name",
  "parentUuid": "B47C7EF7-E7B3-4FD5-B7B8-B4C4CA78BBD9"
}
```

---

## Scenario 4 - Nulstilling af sektion

```http
PATCH /api/v2/{resource}/{uuid}
```

```json
{
  "general": null
}
```

Dette nulstiller hele sektionen og alle underliggende felter.

---

# Forretningsregler

De samme forretningsregler og begrænsninger som findes i KITOS UI gælder fortsat ved anvendelse af API'et.

---

# Vejledning til rettighedshavere

Der findes særskilte endpoints for rettighedshavere.

Se den dedikerede vejledning for rettighedshaveradgang.

---

# Swagger

Den fulde API-dokumentation findes i Swagger-dokumentationen.