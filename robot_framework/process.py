"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
from office365.sharepoint.client_context import ClientContext

from robot_framework import config
from src.kitos_client import KitosClient
from src.mapper import map_kitos_to_sharepoint
from src.sharepoint_client import SharePointClient


def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Synkroniser aktive KITOS-systemer fra MTM-listen til SharePoint."""
    orchestrator_connection.log_trace("KITOS SharePoint sync starter.")

    kitos_cred = orchestrator_connection.get_credential(config.KITOS_CREDENTIAL)
    api_cred   = orchestrator_connection.get_credential(config.SHAREPOINT_API_CREDENTIAL)
    cert_cred  = orchestrator_connection.get_credential(config.SHAREPOINT_CERT_CREDENTIAL)
    site_url   = orchestrator_connection.get_constant(config.SHAREPOINT_URL_CONSTANT)

    sp_ctx = ClientContext(site_url).with_client_certificate(
        tenant=api_cred.username,
        client_id=api_cred.password,
        thumbprint=cert_cred.username,
        cert_path=cert_cred.password,
    )

    sp    = SharePointClient(ctx=sp_ctx)
    kitos = KitosClient(email=kitos_cred.username, password=kitos_cred.password)

    active_uuids = sp.get_active_mtm_uuids()
    orchestrator_connection.log_trace(f"Fandt {len(active_uuids)} aktive systemer i MTM-listen.")

    if not active_uuids:
        orchestrator_connection.log_trace("Ingen aktive systemer — sync afsluttet.")
        return

    created = updated = skipped = errors = 0

    for uuid in active_uuids:
        try:
            system = kitos.get_it_system_usage_by_uuid(uuid)
            if not system:
                orchestrator_connection.log_trace(f"UUID {uuid} ikke fundet i KITOS — springer over.")
                skipped += 1
                continue

            dprs    = kitos.get_dprs_for_system_usage(system["uuid"])
            sp_data = map_kitos_to_sharepoint(system, dprs)
            action  = sp.upsert_sync_item(sp_data)

            if action == "created":
                created += 1
            else:
                updated += 1

            orchestrator_connection.log_trace(f"[{action.upper()}] {sp_data.get('Title', uuid)}")

        except Exception as e:
            errors += 1
            orchestrator_connection.log_error(f"Fejl ved synkronisering af {uuid}: {e}")

    orchestrator_connection.log_trace(
        f"Sync færdig — oprettet: {created}, opdateret: {updated}, sprunget: {skipped}, fejl: {errors}"
    )

    if errors:
        raise RuntimeError(f"{errors} systemer fejlede under synkronisering.")
