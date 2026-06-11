import pytest
from unittest.mock import patch, MagicMock

from src.sharepoint_client import SharePointClient


def _make_sp_item(uuid: str = None, active_sync: bool = None, item_id: int = 1) -> MagicMock:
    item = MagicMock()
    props = {"ID": item_id}
    if uuid:
        props["KitosUUID"] = uuid
    if active_sync is not None:
        props["AktivSync"] = active_sync
    item.properties = props
    return item


def _make_ctx_mock(items: list, filter_items: list = None) -> MagicMock:
    mock_ctx = MagicMock()
    list_mock = mock_ctx.web.lists.get_by_title.return_value
    list_mock.items.get.return_value.execute_query.return_value = items
    list_mock.items.filter.return_value.get.return_value.execute_query.return_value = (
        filter_items if filter_items is not None else items
    )
    return mock_ctx


@pytest.fixture
def client():
    with patch("src.sharepoint_client.ClientContext"):
        with patch("src.sharepoint_client.UserCredential"):
            c = SharePointClient()
            yield c


# --- Context caching ---

def test_get_context_caches(client):
    mock_ctx = MagicMock()
    with patch("src.sharepoint_client.ClientContext") as MockCtx:
        MockCtx.return_value.with_credentials.return_value = mock_ctx
        client._ctx = None
        ctx1 = client._get_context()
        ctx2 = client._get_context()
    assert ctx1 is ctx2
    assert MockCtx.call_count == 1


# --- get_active_mtm_uuids ---

def test_get_active_mtm_uuids_success(client):
    active_items = [
        _make_sp_item("uuid-a", True, 1),
        _make_sp_item("uuid-b", True, 2),
    ]
    client._ctx = _make_ctx_mock([], filter_items=active_items)
    result = client.get_active_mtm_uuids()
    assert result == ["uuid-a", "uuid-b"]


def test_get_active_mtm_uuids_filters_inactive(client):
    # filter_items indeholder kun de aktive (SharePoint filteret klarer det)
    active_items = [_make_sp_item("uuid-aktiv", True, 1)]
    client._ctx = _make_ctx_mock([], filter_items=active_items)
    result = client.get_active_mtm_uuids()
    assert result == ["uuid-aktiv"]


def test_get_active_mtm_uuids_skips_missing_uuid(client, caplog):
    import logging
    items = [
        _make_sp_item("uuid-a", True, 1),
        _make_sp_item(None, True, 2),   # mangler KitosUUID
    ]
    client._ctx = _make_ctx_mock([], filter_items=items)
    with caplog.at_level(logging.WARNING, logger="src.sharepoint_client"):
        result = client.get_active_mtm_uuids()
    assert result == ["uuid-a"]
    assert any("ID=2" in r.message for r in caplog.records)


def test_get_active_mtm_uuids_empty(client):
    client._ctx = _make_ctx_mock([], filter_items=[])
    assert client.get_active_mtm_uuids() == []


def test_get_active_mtm_uuids_raises_on_error(client, caplog):
    import logging
    mock_ctx = MagicMock()
    (mock_ctx.web.lists.get_by_title.return_value
     .items.filter.return_value
     .get.return_value
     .execute_query.side_effect) = Exception("Adgang nægtet")
    client._ctx = mock_ctx
    with caplog.at_level(logging.ERROR, logger="src.sharepoint_client"):
        with pytest.raises(Exception, match="Adgang nægtet"):
            client.get_active_mtm_uuids()
    assert any("Fejl ved læsning af MTM-liste" in r.message for r in caplog.records)


# --- get_all_mtm_uuids ---

def test_get_all_mtm_uuids(client):
    items = [
        _make_sp_item("uuid-a", True, 1),
        _make_sp_item("uuid-b", False, 2),  # inaktiv — medtages alligevel
        _make_sp_item("uuid-c", True, 3),
    ]
    client._ctx = _make_ctx_mock(items)
    result = client.get_all_mtm_uuids()
    assert set(result) == {"uuid-a", "uuid-b", "uuid-c"}


# --- get_sync_item_by_uuid ---

def test_get_sync_item_found(client):
    item = _make_sp_item("uuid-xyz", item_id=5)
    mock_ctx = MagicMock()
    (mock_ctx.web.lists.get_by_title.return_value
     .items.filter.return_value
     .get.return_value
     .execute_query.return_value) = [item]
    client._ctx = mock_ctx
    result = client.get_sync_item_by_uuid("uuid-xyz")
    assert result == item.properties


def test_get_sync_item_not_found(client):
    mock_ctx = MagicMock()
    (mock_ctx.web.lists.get_by_title.return_value
     .items.filter.return_value
     .get.return_value
     .execute_query.return_value) = []
    client._ctx = mock_ctx
    assert client.get_sync_item_by_uuid("ukendt") is None


# --- get_all_sync_uuids ---

def test_get_all_sync_uuids(client):
    items = [_make_sp_item("s-uuid-1"), _make_sp_item("s-uuid-2")]
    client._ctx = _make_ctx_mock(items)
    result = client.get_all_sync_uuids()
    assert set(result) == {"s-uuid-1", "s-uuid-2"}
