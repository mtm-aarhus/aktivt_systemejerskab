from typing import Any, Dict, List, Optional


# Mapping fra KITOS lifeCycleStatus (engelsk) til dansk visningsnavn
_LIFECYCLE_DA = {
    "Operational":      "I drift",
    "Acquired":         "Anskaffet",
    "PreliminaryStudy": "Foranalyse",
    "Development":      "Under udvikling",
    "Testing":          "Test",
    "Pilot":            "Pilot",
    "OutOfService":     "Udgaaet",
    "Undecided":        "Uafklaret",
}


def _safe_get(obj: Optional[Dict], *keys: str, default: Any = None) -> Any:
    """Navigerer sikkert i nestede dicts. Returnerer default hvis et led mangler."""
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _extract_role_name(roles: List[Dict], *patterns: str) -> Optional[str]:
    """Finder første person hvis rollenavn indeholder et af mønstrene (case-insensitiv)."""
    for entry in (roles or []):
        role_name = _safe_get(entry, "role", "name", default="").lower()
        if any(p.lower() in role_name for p in patterns):
            return _safe_get(entry, "user", "name")
    return None


def _dpr_concluded(dprs: Optional[List[Dict]]) -> bool:
    """True hvis mindst én DPR har isAgreementConcluded = 'Yes'."""
    return any(
        _safe_get(d, "general", "isAgreementConcluded") == "Yes"
        for d in (dprs or [])
    )


def _first_dataprocessor(dprs: Optional[List[Dict]]) -> Optional[str]:
    """Navn på første databehandler på tværs af alle DPR'er."""
    for dpr in (dprs or []):
        processors = _safe_get(dpr, "general", "dataProcessors", default=[])
        if processors:
            return processors[0].get("name")
    return None


def map_kitos_to_sharepoint(
    kitos_item: Dict[str, Any],
    dprs: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Mapper KITOS IT-systemanvendelse til SharePoint-feltstruktur.

    Input:
        kitos_item  KITOS læsemodel fra /api/v2/it-system-usages
        dprs        Liste af DPR'er fra /api/v2/data-processing-registrations
                    (systemUsageUuid-filter). Kan udelades — giver Databehandleraftale=False.

    Output:
        dict med interne SharePoint-kolonnenavne klar til upsert.

    Feltmapping:
        uuid                                     → KitosUUID
        systemContext.name                       → Title
        general.localSystemId                    → LokalID
        organizationContext.name                 → Organisation
        lastModified                             → SidstOpdateret
        general.validity.valid (inverteret)      → Deaktiveret
        general.systemUsageCriticalityLevel.name → Kritikalitet
        general.validity.lifeCycleStatus         → Driftstatus (dansk)
        general.mainContract.name                → Kontrakt
        roles[systemejer].user.name              → Systemejer
        roles[it-ansvarlig].user.name            → ITAnsvarlig
        organizationUsage.responsible...name     → Forvalter
        gdpr.directoryDocumentation.url          → GDPRAnmeldelseURL
        gdpr.dataSensitivityLevels               → PersondataKategorier
        gdpr.hostedAt                            → HostetHos
        DPR isAgreementConcluded == 'Yes'        → Databehandleraftale
        DPR general.dataProcessors[0].name       → Databehandler
    """
    roles = kitos_item.get("roles", [])
    sensitivity = (_safe_get(kitos_item, "gdpr", "dataSensitivityLevels") or [])
    lifecycle = _safe_get(kitos_item, "general", "validity", "lifeCycleStatus")
    valid = _safe_get(kitos_item, "general", "validity", "valid", default=True)

    return {
        # Stamfelter
        "KitosUUID":           kitos_item.get("uuid"),
        "Title":               _safe_get(kitos_item, "systemContext", "name"),
        "LokalID":             _safe_get(kitos_item, "general", "localSystemId"),
        "Organisation":        _safe_get(kitos_item, "organizationContext", "name"),
        "SidstOpdateret":      kitos_item.get("lastModified"),
        "Deaktiveret":         not valid,

        # Kritikalitet og drift
        "Kritikalitet":        _safe_get(kitos_item, "general", "systemUsageCriticalityLevel", "name"),
        "Driftstatus":         _LIFECYCLE_DA.get(lifecycle) if lifecycle else None,

        # Kontrakt
        "Kontrakt":            _safe_get(kitos_item, "general", "mainContract", "name"),

        # Roller og ansvar
        "Systemejer":          None,  # Leder af ansvarlig organisationsenhed — sættes eksternt
        "faglig_systemejer":   _extract_role_name(roles, "faglig systemejer"),
        "teknisk_systemejer":  _extract_role_name(roles, "teknisk systemejer"),
        "Forvalter":           _safe_get(kitos_item, "organizationUsage", "responsibleOrganizationUnit", "name"),

        # GDPR
        "GDPRAnmeldelseURL":   _safe_get(kitos_item, "gdpr", "directoryDocumentation", "url"),
        "PersondataKategorier": ", ".join(sensitivity) if sensitivity else None,
        "HostetHos":           _safe_get(kitos_item, "general", "hostedAt"),

        # Databehandleraftale (fra DPR-opslag)
        "Databehandleraftale": _dpr_concluded(dprs),
        "Databehandler":       _first_dataprocessor(dprs),
    }
