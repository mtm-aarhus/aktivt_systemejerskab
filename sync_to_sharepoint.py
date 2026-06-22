"""
KITOS → SharePoint sync via OpenOrchestrator credentials.

Kørsel lokalt (uden Orchestrator — bruger .env):
    python sync_to_sharepoint.py --local

Kørsel fra OpenOrchestrator (produktion):
    python sync_to_sharepoint.py

Kræver i .env (altid):
    KITOS_EMAIL / KITOS_PASSWORD        -- bruges kun ved --local
    SHAREPOINT_URL
    OpenOrchestratorConnString          -- DB-connection string til OO
    OpenOrchestratorKey                 -- krypteringsnøgle til OO

Credentials i OpenOrchestrator (produktion):
    "KitosMTM"       username=email, password=adgangskode til KITOS
    "SharePointAPI"  username=tenant-id, password=client-id (app registration)
    "SharePointCert" username=thumbprint, password=sti til .pem-certifikatfil

Installation:
    pip install OpenOrchestrator
"""

import logging
import os
import sys

from dotenv import load_dotenv
from office365.sharepoint.client_context import ClientContext

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

LOCAL_MODE = "--local" in sys.argv


# ── Credentials ───────────────────────────────────────────────────────────────

def _get_orchestrator_connection():
    """Opretter OrchestratorConnection fra process-argumenter (OO) eller .env (lokal OO-test)."""
    try:
        from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
    except ImportError:
        logger.error(
            "OpenOrchestrator er ikke installeret. Kør: pip install OpenOrchestrator\n"
            "Eller brug --local flaget for at køre med .env-credentials."
        )
        sys.exit(1)

    # OO sender argumenter som: script.py conn_string crypto_key process_args trigger_id job_id
    if len(sys.argv) >= 6:
        conn = OrchestratorConnection("KITOS-Sync", sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        logger.info("OpenOrchestrator forbindelse oprettet via process-argumenter")
    else:
        conn_string = os.getenv("OpenOrchestratorConnString")
        crypto_key  = os.getenv("OpenOrchestratorKey")
        if not conn_string or not crypto_key:
            logger.error("Sæt OpenOrchestratorConnString og OpenOrchestratorKey som miljøvariabler")
            sys.exit(1)
        conn = OrchestratorConnection("KITOS-Sync", conn_string, crypto_key, "", "", "")
        logger.info("OpenOrchestrator forbindelse oprettet via miljøvariabler")

    return conn


def _build_context_from_orchestrator(conn, site_url: str) -> ClientContext:
    """Bygger SharePoint ClientContext med certifikat-credentials fra OpenOrchestrator."""
    cert = conn.get_credential("SharePointCert")
    api  = conn.get_credential("SharePointAPI")

    ctx = ClientContext(site_url).with_client_certificate(
        tenant=api.username,
        client_id=api.password,
        thumbprint=cert.username,
        cert_path=cert.password,
    )
    logger.info("SharePoint context oprettet (certifikat via OpenOrchestrator)")
    return ctx


def _get_kitos_credentials_from_orchestrator(conn) -> tuple[str, str]:
    cred = conn.get_credential("KitosMTM")
    return cred.username, cred.password


def _build_context_local(site_url: str) -> ClientContext:
    """Bygger SharePoint ClientContext med client-secret fra .env (udviklingstilstand)."""
    from office365.runtime.auth.client_credential import ClientCredential
    from src import config

    config.validate_env()
    creds = ClientCredential(config.AZURE_CLIENT_ID, config.AZURE_CLIENT_SECRET)
    ctx = ClientContext(site_url).with_credentials(creds)
    logger.info("SharePoint context oprettet (client secret via .env — lokal tilstand)")
    return ctx


# ── Sync-logik ────────────────────────────────────────────────────────────────

def run_sync(kitos_email: str, kitos_password: str, sp_ctx: ClientContext) -> None:
    from src.kitos_client import KitosClient
    from src.mapper import map_kitos_to_sharepoint
    from src.sharepoint_client import SharePointClient

    sp    = SharePointClient(ctx=sp_ctx)
    kitos = KitosClient(email=kitos_email, password=kitos_password)

    logger.info("=== KITOS SharePoint Sync starter ===")

    active_uuids = sp.get_active_mtm_uuids()
    logger.info(f"Fandt {len(active_uuids)} aktive systemer i MTM-listen")

    if not active_uuids:
        logger.warning("Ingen aktive systemer — sync afsluttet uden ændringer")
        return

    created = updated = skipped = errors = 0

    for uuid in active_uuids:
        try:
            system = kitos.get_it_system_usage_by_uuid(uuid)
            if not system:
                logger.warning(f"UUID {uuid} ikke fundet i KITOS — springer over")
                skipped += 1
                continue

            dprs    = kitos.get_dprs_for_system_usage(system["uuid"])
            sp_data = map_kitos_to_sharepoint(system, dprs)
            action  = sp.upsert_sync_item(sp_data)

            if action == "created":
                created += 1
            else:
                updated += 1

            logger.info(f"[{action.upper()}] {sp_data.get('Title', uuid)}")

        except Exception as e:
            logger.error(f"Fejl ved synkronisering af {uuid}: {e}")
            errors += 1

    logger.info("=== Sync færdig ===")
    logger.info(f"  Oprettet : {created}")
    logger.info(f"  Opdateret: {updated}")
    logger.info(f"  Sprunget : {skipped}")
    logger.info(f"  Fejl     : {errors}")

    if errors:
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if LOCAL_MODE:
        site_url = os.getenv("SHAREPOINT_URL")
        if not site_url:
            logger.error("SHAREPOINT_URL mangler i .env")
            sys.exit(1)
        from src import config
        sp_ctx = _build_context_local(site_url)
        email    = config.KITOS_EMAIL
        password = config.KITOS_PASSWORD
    else:
        conn     = _get_orchestrator_connection()
        site_url = conn.get_constant("aktivt_systemejerskab_sharepoint")
        sp_ctx   = _build_context_from_orchestrator(conn, site_url)
        email, password = _get_kitos_credentials_from_orchestrator(conn)

    run_sync(email, password, sp_ctx)


if __name__ == "__main__":
    main()
