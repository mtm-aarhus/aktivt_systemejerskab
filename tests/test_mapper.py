import pytest
from src.mapper import map_kitos_to_sharepoint, _safe_get, _extract_role_name, _dpr_concluded, _first_dataprocessor

# --- Testdata ---

_FULL_ITEM = {
    "uuid": "ae564995-da3d-4e58-bb0b-b986b3b83f52",
    "lastModified": "2026-04-16T06:46:37Z",
    "systemContext": {"uuid": "aaa", "name": "Microsoft 365"},
    "organizationContext": {"cvr": "55133018", "uuid": "bbb", "name": "Aarhus Kommune"},
    "general": {
        "localSystemId": "IT-1234",
        "validity": {
            "valid": True,
            "lifeCycleStatus": "Operational",
        },
        "systemUsageCriticalityLevel": {"uuid": "ccc", "name": "Hoj"},
        "mainContract": {"uuid": "ddd", "name": "Microsoft licenser"},
    },
    "roles": [
        {"user": {"uuid": "u1", "name": "Anne Nielsen"},  "role": {"uuid": "r1", "name": "Faglig systemejer"}},
        {"user": {"uuid": "u2", "name": "Mette Sorensen"}, "role": {"uuid": "r2", "name": "IT-ansvarlig"}},
        {"user": {"uuid": "u3", "name": "Lars Jorgensen"}, "role": {"uuid": "r3", "name": "Superbruger"}},
    ],
    "organizationUsage": {
        "responsibleOrganizationUnit": {"uuid": "o1", "name": "Digitale Losninger"},
    },
    "gdpr": {
        "hostedAt": "External",
        "dataSensitivityLevels": ["PersonData", "SensitiveData"],
        "directoryDocumentation": {
            "name": "Anmeldelse",
            "url": "https://aarhus.sharepoint.com/anmeldelse?ID=42",
        },
    },
}

_FULL_DPRS = [
    {
        "uuid": "dpr-1",
        "general": {
            "isAgreementConcluded": "Yes",
            "dataProcessors": [
                {"cvr": "12345678", "uuid": "p1", "name": "KMD A/S"},
                {"cvr": "87654321", "uuid": "p2", "name": "Systematic A/S"},
            ],
        },
    }
]


# --- _safe_get ---

def test_safe_get_existing():
    assert _safe_get({"a": {"b": "v"}}, "a", "b") == "v"

def test_safe_get_missing_intermediate():
    assert _safe_get({"a": None}, "a", "b") is None

def test_safe_get_missing_key():
    assert _safe_get({}, "a") is None

def test_safe_get_custom_default():
    assert _safe_get({}, "a", default="x") == "x"

def test_safe_get_none_input():
    assert _safe_get(None, "a") is None


# --- _extract_role_name ---

def test_extract_role_systemejer():
    roles = _FULL_ITEM["roles"]
    assert _extract_role_name(roles, "systemejer") == "Anne Nielsen"

def test_extract_role_it_ansvarlig():
    roles = _FULL_ITEM["roles"]
    assert _extract_role_name(roles, "it-ansvarlig") == "Mette Sorensen"

def test_extract_role_not_found():
    roles = _FULL_ITEM["roles"]
    assert _extract_role_name(roles, "leverandor") is None

def test_extract_role_empty():
    assert _extract_role_name([], "systemejer") is None


# --- _dpr_concluded ---

def test_dpr_concluded_yes():
    assert _dpr_concluded(_FULL_DPRS) is True

def test_dpr_concluded_no():
    dprs = [{"general": {"isAgreementConcluded": "No"}}]
    assert _dpr_concluded(dprs) is False

def test_dpr_concluded_empty():
    assert _dpr_concluded([]) is False

def test_dpr_concluded_none():
    assert _dpr_concluded(None) is False


# --- _first_dataprocessor ---

def test_first_dataprocessor():
    assert _first_dataprocessor(_FULL_DPRS) == "KMD A/S"

def test_first_dataprocessor_empty():
    assert _first_dataprocessor([]) is None

def test_first_dataprocessor_no_processors():
    dprs = [{"general": {"dataProcessors": []}}]
    assert _first_dataprocessor(dprs) is None


# --- map_kitos_to_sharepoint: fuldt udfyldt ---

def test_full_mapping_stamfelter():
    r = map_kitos_to_sharepoint(_FULL_ITEM, _FULL_DPRS)
    assert r["KitosUUID"] == "ae564995-da3d-4e58-bb0b-b986b3b83f52"
    assert r["Title"] == "Microsoft 365"
    assert r["LokalID"] == "IT-1234"
    assert r["Organisation"] == "Aarhus Kommune"
    assert r["SidstOpdateret"] == "2026-04-16T06:46:37Z"
    assert r["Deaktiveret"] is False

def test_full_mapping_drift():
    r = map_kitos_to_sharepoint(_FULL_ITEM, _FULL_DPRS)
    assert r["Driftstatus"] == "I drift"
    assert r["Kritikalitet"] == "Hoj"
    assert r["Kontrakt"] == "Microsoft licenser"

def test_full_mapping_roller():
    r = map_kitos_to_sharepoint(_FULL_ITEM, _FULL_DPRS)
    assert r["Systemejer"] == "Anne Nielsen"
    assert r["ITAnsvarlig"] == "Mette Sorensen"
    assert r["Forvalter"] == "Digitale Losninger"

def test_full_mapping_gdpr():
    r = map_kitos_to_sharepoint(_FULL_ITEM, _FULL_DPRS)
    assert r["GDPRAnmeldelseURL"] == "https://aarhus.sharepoint.com/anmeldelse?ID=42"
    assert r["PersondataKategorier"] == "PersonData, SensitiveData"
    assert r["HostetHos"] == "External"

def test_full_mapping_dpr():
    r = map_kitos_to_sharepoint(_FULL_ITEM, _FULL_DPRS)
    assert r["Databehandleraftale"] is True
    assert r["Databehandler"] == "KMD A/S"


# --- Uden DPR ---

def test_no_dprs_gives_false():
    r = map_kitos_to_sharepoint(_FULL_ITEM)
    assert r["Databehandleraftale"] is False
    assert r["Databehandler"] is None


# --- Deaktiveret system ---

def test_deactivated_inverts_valid():
    item = {**_FULL_ITEM, "general": {**_FULL_ITEM["general"], "validity": {"valid": False, "lifeCycleStatus": "OutOfService"}}}
    r = map_kitos_to_sharepoint(item)
    assert r["Deaktiveret"] is True
    assert r["Driftstatus"] == "Udgaaet"


# --- Lifecycle mapping ---

def test_lifecycle_alle_vaerdier():
    from src.mapper import _LIFECYCLE_DA
    expected = {"Operational", "Acquired", "PreliminaryStudy", "Development",
                "Testing", "Pilot", "OutOfService", "Undecided"}
    assert set(_LIFECYCLE_DA.keys()) == expected


# --- Minimalt item ---

def test_minimal_item():
    r = map_kitos_to_sharepoint({"uuid": "min"})
    assert r["KitosUUID"] == "min"
    assert r["Title"] is None
    assert r["Deaktiveret"] is False
    assert r["Databehandleraftale"] is False


# --- Output-nøgler ---

def test_output_keys():
    r = map_kitos_to_sharepoint(_FULL_ITEM)
    expected = {
        "KitosUUID", "Title", "LokalID", "Organisation", "SidstOpdateret", "Deaktiveret",
        "Kritikalitet", "Driftstatus", "Kontrakt",
        "Systemejer", "ITAnsvarlig", "Forvalter",
        "GDPRAnmeldelseURL", "PersondataKategorier", "HostetHos",
        "Databehandleraftale", "Databehandler",
    }
    assert set(r.keys()) == expected
