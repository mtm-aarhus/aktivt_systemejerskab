"""
KITOS → SharePoint synkronisering
Entry point for OpenOrchestrator (python -m src.main)
"""

import logging
import sys

from . import config
from .kitos_client import KitosClient
from .mapper import map_kitos_to_sharepoint
from .sharepoint_client import SharePointClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    config.validate_env()
    logger.info("=== KITOS SharePoint Sync starter ===")

    sp = SharePointClient()
    kitos = KitosClient()

    # 1. Hent aktive UUID'er fra MTM-listen
    active_uuids = sp.get_active_mtm_uuids()
    logger.info(f"Fandt {len(active_uuids)} aktive systemer i MTM-listen")

    if not active_uuids:
        logger.warning("Ingen aktive systemer — sync afsluttet uden ændringer")
        return

    # 2. Synkroniser hvert system
    created = updated = skipped = errors = 0

    for uuid in active_uuids:
        try:
            system = kitos.get_it_system_usage_by_uuid(uuid)
            if not system:
                logger.warning(f"UUID {uuid} ikke fundet i KITOS — springer over")
                skipped += 1
                continue

            dprs = kitos.get_dprs_for_system_usage(system["uuid"])
            sp_data = map_kitos_to_sharepoint(system, dprs)
            action = sp.upsert_sync_item(sp_data)

            if action == "created":
                created += 1
            else:
                updated += 1

            logger.info(f"[{action.upper()}] {sp_data.get('Title', uuid)}")

        except Exception as e:
            logger.error(f"Fejl ved synkronisering af {uuid}: {e}")
            errors += 1

    # 3. Opsummering
    logger.info("=== Sync færdig ===")
    logger.info(f"  Oprettet : {created}")
    logger.info(f"  Opdateret: {updated}")
    logger.info(f"  Sprunget : {skipped}")
    logger.info(f"  Fejl     : {errors}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
