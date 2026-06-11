import pytest
from unittest.mock import patch, MagicMock
import requests

from src.kitos_client import KitosClient

# --- Testdata ---

_AUTH_RESPONSE = {
    "msg": "",
    "response": {
        "token": "test-jwt-token-abc123",
        "email": "svc@test.dk",
        "loginSuccessful": True,
        "expires": "2026-06-10T06:00:00Z",
    },
}

_SYSTEM = {
    "uuid": "673f4775-ede0-49a9-9e27-f46c69ddf5c6",
    "name": "Beslutningsguide",
    "systemContext": {"uuid": "aaa", "name": "Test Org"},
}


def _make_response(status_code: int, json_data=None) -> MagicMock:
    """Returnerer en mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    if status_code >= 400:
        http_err = requests.exceptions.HTTPError(response=mock)
        mock.raise_for_status.side_effect = http_err
    else:
        mock.raise_for_status.return_value = None
    return mock


@pytest.fixture
def client():
    """KitosClient med mocket auth-kald."""
    with patch("src.kitos_client.requests.post") as mock_post:
        mock_post.return_value = _make_response(200, _AUTH_RESPONSE)
        yield KitosClient()


# --- Test 1: Constructor sætter token korrekt ---

def test_init_sets_token(client):
    assert client._token == "test-jwt-token-abc123"


# --- Test 2: _headers indeholder Bearer token ---

def test_headers_contain_bearer(client):
    headers = client._headers()
    assert headers["Authorization"] == "Bearer test-jwt-token-abc123"
    assert headers["Content-Type"] == "application/json"


# --- Test 3: Vellykket enkelt UUID-opslag ---

def test_get_single_uuid_success(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, [_SYSTEM])
        result = client.get_it_system_usage_by_uuid(_SYSTEM["uuid"])

    assert result is not None
    assert result["uuid"] == _SYSTEM["uuid"]
    assert result["name"] == "Beslutningsguide"


# --- Test 4: Tomt svar giver None ---

def test_get_single_uuid_empty_response(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, [])
        result = client.get_it_system_usage_by_uuid("ukendt-uuid")

    assert result is None


# --- Test 5: 404 giver None (ikke exception) ---

def test_get_single_uuid_404(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(404)
        result = client.get_it_system_usage_by_uuid("ikke-eksisterende-uuid")

    assert result is None


# --- Test 6: HTTP 500 kaster exception ---

def test_get_single_uuid_server_error_raises(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(500)
        with pytest.raises(requests.exceptions.HTTPError):
            client.get_it_system_usage_by_uuid("uuid-x")


# --- Test 7: Batch — blandet resultat (2 fundet, 1 ikke) ---

def test_get_batch_mixed_results(client):
    uuid_a = "aaaa-1111"
    uuid_b = "bbbb-2222"
    uuid_c = "cccc-3333"

    system_a = {**_SYSTEM, "uuid": uuid_a}
    system_b = {**_SYSTEM, "uuid": uuid_b}

    responses = {
        uuid_a: _make_response(200, [system_a]),
        uuid_b: _make_response(200, []),
        uuid_c: _make_response(200, [system_b]),
    }

    call_count = 0

    def side_effect(url, **kwargs):
        nonlocal call_count
        uuid = kwargs.get("params", {}).get("systemUuid")
        call_count += 1
        return responses[uuid]

    with patch("src.kitos_client.requests.get", side_effect=side_effect):
        results = client.get_it_system_usages_for_uuids([uuid_a, uuid_b, uuid_c])

    assert len(results) == 2
    assert call_count == 3


# --- Test 8: Timeout kaster exception ---

def test_get_single_uuid_timeout_raises(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        with pytest.raises(requests.exceptions.Timeout):
            client.get_it_system_usage_by_uuid("uuid-timeout")


# --- Test 9: Forbindelsesfejl kaster exception ---

def test_get_single_uuid_connection_error_raises(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("no route")
        with pytest.raises(requests.exceptions.ConnectionError):
            client.get_it_system_usage_by_uuid("uuid-conn")


# --- Test 10: 401 trigger token-refresh ---

def test_get_retries_on_401(client):
    fresh_response = _make_response(200, [_SYSTEM])
    unauthorized = _make_response(401)

    with patch("src.kitos_client.requests.post") as mock_post, \
         patch("src.kitos_client.requests.get") as mock_get:

        mock_post.return_value = _make_response(200, _AUTH_RESPONSE)
        mock_get.side_effect = [unauthorized, fresh_response]

        result = client.get_it_system_usage_by_uuid(_SYSTEM["uuid"])

    assert result is not None
    assert mock_post.call_count == 1  # én re-auth
    assert mock_get.call_count == 2   # første kald (401) + retry


# --- DPR-opslag ---

_DPR = {
    "uuid": "dpr-uuid-1",
    "general": {
        "isAgreementConcluded": "Yes",
        "dataProcessors": [{"name": "KMD A/S"}],
    },
}


def test_get_dprs_success(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, [_DPR, _DPR])
        result = client.get_dprs_for_system_usage("usage-uuid")

    assert len(result) == 2
    assert result[0]["uuid"] == "dpr-uuid-1"


def test_get_dprs_empty(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(200, [])
        result = client.get_dprs_for_system_usage("usage-uuid")

    assert result == []


def test_get_dprs_404_returns_empty(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(404)
        result = client.get_dprs_for_system_usage("usage-uuid")

    assert result == []


def test_get_dprs_server_error_raises(client):
    with patch("src.kitos_client.requests.get") as mock_get:
        mock_get.return_value = _make_response(500)
        with pytest.raises(requests.exceptions.HTTPError):
            client.get_dprs_for_system_usage("usage-uuid")
