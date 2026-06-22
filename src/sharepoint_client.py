import logging
from typing import List, Optional, Dict, Any

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

from . import config

logger = logging.getLogger(__name__)

_KITOS_UUID_FIELD = "KitosUUID"


class SharePointClient:
    def __init__(self, ctx: Optional[ClientContext] = None):
        self.mtm_list_name = config.MTM_LIST
        self.mtm_active_field = config.MTM_ACTIVE_FIELD
        self.sync_list_name = config.SHAREPOINT_SYNC_LIST
        self._ctx: Optional[ClientContext] = ctx
        self._build_from_config = ctx is None

    # --- Forbindelse ---

    def _get_context(self) -> ClientContext:
        if self._ctx is None and self._build_from_config:
            credentials = ClientCredential(config.AZURE_CLIENT_ID, config.AZURE_CLIENT_SECRET)
            self._ctx = ClientContext(config.SHAREPOINT_URL).with_credentials(credentials)
            logger.info("SharePoint context oprettet (client secret)")
        return self._ctx

    # --- MTM-liste: læs ---

    def get_all_mtm_items(self) -> List[Dict[str, Any]]:
        """Henter alle items fra MTM-listen med uuid, item-id og aktiv-status."""
        try:
            ctx = self._get_context()
            items = (
                ctx.web.lists.get_by_title(self.mtm_list_name)
                .items.get()
                .execute_query()
            )
            result = []
            for item in items:
                uuid = item.properties.get(_KITOS_UUID_FIELD)
                if uuid:
                    result.append({
                        "uuid": uuid,
                        "id": item.properties.get("ID"),
                        "active": bool(item.properties.get(self.mtm_active_field)),
                    })
            logger.info(f"Hentet {len(result)} items fra '{self.mtm_list_name}'")
            return result
        except Exception as e:
            logger.error(f"Fejl ved læsning af MTM-liste: {e}")
            raise

    def get_active_mtm_uuids(self) -> List[str]:
        """Henter UUID'er for alle MTM-systemer hvor AktivSync = Ja."""
        try:
            ctx = self._get_context()
            items = (
                ctx.web.lists.get_by_title(self.mtm_list_name)
                .items.filter(f"{self.mtm_active_field} eq 1")
                .get()
                .execute_query()
            )
            uuids: List[str] = []
            for item in items:
                uuid = item.properties.get(_KITOS_UUID_FIELD)
                if uuid:
                    uuids.append(uuid)
                else:
                    logger.warning(
                        f"MTM-item ID={item.properties.get('ID')} "
                        f"har AktivSync=Ja men mangler '{_KITOS_UUID_FIELD}' — springes over"
                    )
            logger.info(f"Hentet {len(uuids)} aktive UUID'er fra '{self.mtm_list_name}'")
            return uuids
        except Exception as e:
            logger.error(f"Fejl ved læsning af MTM-liste: {e}")
            raise

    # --- MTM-liste: skriv ---

    def add_mtm_item(self, uuid: str, title: str) -> None:
        """Tilføjer ét system til MTM-listen med AktivSync = Ja.

        Springer over hvis UUID allerede findes.
        """
        try:
            ctx = self._get_context()
            ctx.web.lists.get_by_title(self.mtm_list_name).items.add({
                "Title": title,
                _KITOS_UUID_FIELD: uuid,
                self.mtm_active_field: True,
            }).execute_query()
            logger.debug(f"Tilføjet til MTM-listen: {title} ({uuid})")
        except Exception as e:
            logger.error(f"Fejl ved oprettelse af MTM-item {uuid}: {e}")
            raise

    def deactivate_mtm_item(self, item_id: int, uuid: str) -> None:
        """Sætter AktivSync = Nej for et MTM-item (system forsvundet fra KITOS)."""
        try:
            ctx = self._get_context()
            item = ctx.web.lists.get_by_title(self.mtm_list_name).items.get_by_id(item_id)
            item.set_property(self.mtm_active_field, False)
            item.update().execute_query()
            logger.debug(f"Deaktiveret MTM-item ID={item_id} ({uuid})")
        except Exception as e:
            logger.error(f"Fejl ved deaktivering af MTM-item {uuid}: {e}")
            raise

    # --- Synkliste: opslag ---

    def get_sync_item_by_uuid(self, kitos_uuid: str) -> Optional[Dict[str, Any]]:
        """Finder eksisterende item i synklisten ud fra KITOS UUID."""
        try:
            ctx = self._get_context()
            items = (
                ctx.web.lists.get_by_title(self.sync_list_name)
                .items.filter(f"{_KITOS_UUID_FIELD} eq '{kitos_uuid}'")
                .get()
                .execute_query()
            )
            if items:
                logger.debug(f"Fandt eksisterende item for UUID {kitos_uuid}")
                return items[0].properties
            logger.debug(f"Ingen eksisterende item for UUID {kitos_uuid}")
            return None
        except Exception as e:
            logger.error(f"Fejl ved opslag af sync-item {kitos_uuid}: {e}")
            raise

    def get_all_sync_uuids(self) -> List[str]:
        """Henter alle KITOS UUID'er i synklisten."""
        try:
            ctx = self._get_context()
            items = (
                ctx.web.lists.get_by_title(self.sync_list_name)
                .items.get()
                .execute_query()
            )
            uuids = [
                item.properties[_KITOS_UUID_FIELD]
                for item in items
                if item.properties.get(_KITOS_UUID_FIELD)
            ]
            logger.info(f"Hentet {len(uuids)} eksisterende UUID'er fra synklisten")
            return uuids
        except Exception as e:
            logger.error(f"Fejl ved læsning af sync-UUID'er: {e}")
            raise

    # --- Synkliste: skriv ---

    def upsert_sync_item(self, sp_data: Dict[str, Any]) -> str:
        """Opretter eller opdaterer item i synklisten baseret på KitosUUID.

        Returnerer 'created' eller 'updated'.
        """
        kitos_uuid = sp_data[_KITOS_UUID_FIELD]
        try:
            ctx = self._get_context()
            existing = self.get_sync_item_by_uuid(kitos_uuid)
            clean_data = _clean_for_sharepoint(sp_data)

            if existing:
                item_id = existing["ID"]
                item = ctx.web.lists.get_by_title(self.sync_list_name).items.get_by_id(item_id)
                for key, value in clean_data.items():
                    item.set_property(key, value)
                item.update().execute_query()
                logger.debug(f"Opdateret item for UUID {kitos_uuid}")
                return "updated"

            ctx.web.lists.get_by_title(self.sync_list_name).items.add(clean_data).execute_query()
            logger.debug(f"Oprettet item for UUID {kitos_uuid}")
            return "created"
        except Exception as e:
            logger.error(f"Fejl ved upsert af {kitos_uuid}: {e}")
            raise

    def delete_sync_item(self, kitos_uuid: str) -> None:
        """Sletter item fra synklisten hvis det eksisterer."""
        try:
            existing = self.get_sync_item_by_uuid(kitos_uuid)
            if not existing:
                return
            ctx = self._get_context()
            ctx.web.lists.get_by_title(self.sync_list_name) \
                .items.get_by_id(existing["ID"]) \
                .delete_object() \
                .execute_query()
            logger.debug(f"Slettet sync-item for UUID {kitos_uuid}")
        except Exception as e:
            logger.error(f"Fejl ved sletning af sync-item {kitos_uuid}: {e}")
            raise


# --- Hjælpefunktioner ---

def _clean_for_sharepoint(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fjerner None-værdier og formaterer URL-felter korrekt."""
    result = {}
    url_fields = {"GDPRAnmeldelseURL"}
    for key, value in data.items():
        if value is None:
            continue
        if key in url_fields and isinstance(value, str):
            result[key] = {"__metadata": {"type": "SP.FieldUrlValue"},
                           "Url": value, "Description": value}
        else:
            result[key] = value
    return result
