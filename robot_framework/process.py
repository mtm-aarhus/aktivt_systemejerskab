"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
from office365.sharepoint.client_context import ClientContext

from robot_framework import config
from src.kitos_client import KitosClient
from src.mapper import map_kitos_to_sharepoint
from src.sharepoint_client import SharePointClient


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Synkroniser aktive KITOS-systemer fra MTM-listen til SharePoint."""
    orchestrator_connection.log_info("Henter credentials fra OpenOrchestrator...")

    kitos_cred = orchestrator_connection.get_credential(config.KITOS_CREDENTIAL)
    orchestrator_connection.log_info(f"KitosMTM credential hentet: {kitos_cred.username}")

    api_cred  = orchestrator_connection.get_credential(config.SHAREPOINT_API_CREDENTIAL)
    orchestrator_connection.log_info(f"SharePointAPI credential hentet: {api_cred.username}")

    cert_cred = orchestrator_connection.get_credential(config.SHAREPOINT_CERT_CREDENTIAL)
    orchestrator_connection.log_info(f"SharePointCert credential hentet (thumbprint: {cert_cred.username[:8]}...)")

    site_url = orchestrator_connection.get_constant(config.SHAREPOINT_URL_CONSTANT)
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

    orchestrator_connection.log_info(f"Henter aktive systemer fra MTM-listen: '{config.MTM_LIST}'...")
    active_uuids = sp.get_active_mtm_uuids()
    orchestrator_connection.log_info(f"Fandt {len(active_uuids)} aktive systemer i MTM-listen.")

    if not active_uuids:
        orchestrator_connection.log_info("Ingen aktive systemer — sync afsluttet uden ændringer.")
        return

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
        f"=== Sync færdig === Oprettet: {created} | Opdateret: {updated} | Sprunget over: {skipped} | Fejl: {errors}"
    )

    if errors:
        raise RuntimeError(f"{errors} systemer fejlede under synkronisering.")
