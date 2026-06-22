"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
from office365.sharepoint.client_context import ClientContext

from robot_framework import config
from src.kitos_client import KitosClient
from src.mapper import map_kitos_to_sharepoint
from src.sharepoint_client import SharePointClient


def _is_mtm_system(system: dict) -> bool:
    """Returnerer True hvis systemet tilhører MTM (Teknik og Miljø)."""
    org = system.get("organizationUsage") or {}
    ansvarlig = (org.get("responsibleOrganizationUnit") or {}).get("name", "").lower()
    brugende = [
        u.get("name", "").lower()
        for u in (org.get("usingOrganizationUnits") or [])
    ]
    for enhed in [ansvarlig] + brugende:
        if any(kw in enhed for kw in config.MTM_KEYWORDS):
            return True
        if any(unit == enhed or unit in enhed for unit in config.MTM_UNITS_WHITELIST):
            return True
    return False


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Synkroniser KITOS-systemer til SharePoint — tilføj nye, deaktiver fjernede, opdater eksisterende."""
    orchestrator_connection.log_info("Henter credentials fra OpenOrchestrator...")

    kitos_cred = orchestrator_connection.get_credential(config.KITOS_CREDENTIAL)
    orchestrator_connection.log_info(f"KitosMTM credential hentet: {kitos_cred.username}")

    api_cred  = orchestrator_connection.get_credential(config.SHAREPOINT_API_CREDENTIAL)
    orchestrator_connection.log_info(f"SharePointAPI credential hentet: {api_cred.username}")

    cert_cred = orchestrator_connection.get_credential(config.SHAREPOINT_CERT_CREDENTIAL)
    orchestrator_connection.log_info(f"SharePointCert credential hentet (thumbprint: {cert_cred.username[:8]}...)")

    site_url = orchestrator_connection.get_constant(config.SHAREPOINT_URL_CONSTANT).value
    orchestrator_connection.log_info(f"SharePoint URL: {site_url}")

    orchestrator_connection.log_info("Opretter SharePoint forbindelse med certifikat...")
    sp_ctx = ClientContext(site_url).with_client_certificate(
        tenant=api_cred.username,
        client_id=api_cred.password,
        thumbprint=cert_cred.username,
        cert_path=cert_cred.password,
    )

    orchestrator_connection.log_info("Logger ind i KITOS...")
    kitos = KitosClient(email=kitos_cred.username, password=kitos_cred.password)
    orchestrator_connection.log_info("KITOS login OK.")

    sp = SharePointClient(ctx=sp_ctx)

    # --- Trin 1: Hent alle systemer fra KITOS og filtrer på MTM ---
    orchestrator_connection.log_info("Henter alle systemer fra KITOS...")
    all_systems = kitos.get_all_system_usages()
    mtm_systems = [s for s in all_systems if _is_mtm_system(s)]
    kitos_by_uuid = {s["uuid"]: s for s in mtm_systems if s.get("uuid")}
    orchestrator_connection.log_info(
        f"Hentede {len(all_systems)} systemer i alt — filtreret til {len(kitos_by_uuid)} MTM-systemer."
    )

    # --- Trin 2: Hent alle items fra MTM-listen ---
    orchestrator_connection.log_info(f"Henter alle items fra MTM-listen '{config.MTM_LIST}'...")
    mtm_items = sp.get_all_mtm_items()
    mtm_by_uuid = {item["uuid"]: item for item in mtm_items}
    orchestrator_connection.log_info(f"Fandt {len(mtm_by_uuid)} items i MTM-listen.")

    # --- Trin 3: Tilføj nye systemer (i KITOS men ikke i MTM-listen) ---
    new_uuids = set(kitos_by_uuid) - set(mtm_by_uuid)
    add_errors = 0
    if new_uuids:
        orchestrator_connection.log_info(f"Tilføjer {len(new_uuids)} nye systemer til MTM-listen...")
        for uuid in new_uuids:
            title = kitos_by_uuid[uuid].get("systemContext", {}).get("name", uuid)
            try:
                sp.add_mtm_item(uuid, title)
                orchestrator_connection.log_info(f"  [NY] {title}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                add_errors += 1
                orchestrator_connection.log_error(f"  Fejl ved tilføjelse af {title} ({uuid}): {e}")

    # --- Trin 4: Deaktiver fjernede systemer (i MTM-listen men ikke i KITOS) ---
    removed_uuids = set(mtm_by_uuid) - set(kitos_by_uuid)
    if removed_uuids:
        orchestrator_connection.log_info(f"Deaktiverer {len(removed_uuids)} systemer forsvundet fra KITOS...")
        for uuid in removed_uuids:
            item = mtm_by_uuid[uuid]
            if item["active"]:
                sp.deactivate_mtm_item(item["id"], uuid)
                orchestrator_connection.log_info(f"  [DEAKTIVERET] {uuid}")
            sp.delete_sync_item(uuid)
            orchestrator_connection.log_info(f"  [SLETTET FRA SYNKLISTE] {uuid}")

    # --- Trin 5: Hent opdateret liste af aktive UUID'er ---
    active_uuids = sp.get_active_mtm_uuids()
    orchestrator_connection.log_info(f"Aktive systemer til sync: {len(active_uuids)}")

    if not active_uuids:
        orchestrator_connection.log_info("Ingen aktive systemer — sync afsluttet.")
        return

    # --- Trin 6: Synkroniser aktive systemer til IT-Systemer KITOS ---
    created = updated = skipped = errors = 0

    for i, system_uuid in enumerate(active_uuids, 1):
        try:
            orchestrator_connection.log_info(f"[{i}/{len(active_uuids)}] Behandler UUID: {system_uuid}")

            system = kitos.get_it_system_usage_by_uuid(system_uuid)
            if not system:
                orchestrator_connection.log_info(f"  UUID {system_uuid} ikke fundet i KITOS — springer over.")
                skipped += 1
                continue

            title = system.get("systemContext", {}).get("name", system_uuid)
            dprs    = kitos.get_dprs_for_system_usage(system["uuid"])
            sp_data = map_kitos_to_sharepoint(system, dprs)
            action  = sp.upsert_sync_item(sp_data)

            if action == "created":
                created += 1
            else:
                updated += 1

            orchestrator_connection.log_info(f"  [{action.upper()}] {title}")

        except Exception as e:  # pylint: disable=broad-exception-caught
            errors += 1
            orchestrator_connection.log_error(f"  Fejl ved synkronisering af {system_uuid}: {e}")

    orchestrator_connection.log_info(
        f"=== Sync færdig === Nye: {len(new_uuids)} | Tilføjelsesfejl: {add_errors} | "
        f"Fjernede: {len(removed_uuids)} | "
        f"Oprettet: {created} | Opdateret: {updated} | Sprunget over: {skipped} | Fejl: {errors}"
    )

    if add_errors or errors:
        raise RuntimeError(f"{add_errors} tilføjelsesfejl og {errors} synkfejl under kørsel.")
