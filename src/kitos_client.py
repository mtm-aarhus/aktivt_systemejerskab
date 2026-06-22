import logging
from typing import Optional, List, Dict, Any

import requests

from . import config

logger = logging.getLogger(__name__)

_AUTH_URL = "https://kitos.dk/api/authorize/GetToken"


class KitosClient:
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        self.base_url = config.KITOS_BASE_URL.rstrip("/")
        self._email = email or config.KITOS_EMAIL
        self._password = password or config.KITOS_PASSWORD
        self._token: Optional[str] = None
        self._authenticate()

    # --- Auth ---

    def _authenticate(self) -> None:
        logger.debug("Henter KITOS Bearer token")
        try:
            resp = requests.post(
                _AUTH_URL,
                json={"email": self._email, "password": self._password},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Autentifikation mod KITOS fejlede: {e}")
            raise

        data = resp.json()
        self._token = data["response"]["token"]
        logger.debug("KITOS Bearer token modtaget")

    # --- Intern HTTP-hjælper ---

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        logger.debug(f"GET {url} params={params}")

        try:
            resp = requests.get(
                url, headers=self._headers(), params=params, timeout=30
            )
            # Forsøg token-refresh ved 401
            if resp.status_code == 401:
                logger.info("Token udløbet — genautentificerer")
                self._authenticate()
                resp = requests.get(
                    url, headers=self._headers(), params=params, timeout=30
                )
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.error(f"Timeout ved kald til {url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Forbindelsesfejl ved kald til {url}")
            raise

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # --- Subtask 3.2: Enkelt UUID-opslag ---

    def get_it_system_usage_by_uuid(
        self, system_uuid: str
    ) -> Optional[Dict[str, Any]]:
        """Henter IT-systemanvendelse for ét UUID. Returnerer None hvis ikke fundet."""
        try:
            data = self._get(
                "/it-system-usages",
                {"systemUuid": system_uuid, "page": 0, "pageSize": 1},
            )
            if data:
                return data[0]
            return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"IT-system med UUID {system_uuid} ikke fundet")
                return None
            logger.error(f"HTTP fejl ved opslag af {system_uuid}: {e}")
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Fejl ved opslag af {system_uuid}: {e}")
            raise

    # --- Subtask 3.3: Batch-opslag ---

    def get_it_system_usages_for_uuids(
        self, uuids: List[str]
    ) -> List[Dict[str, Any]]:
        """Henter IT-systemanvendelser for en liste af UUID'er.
        UUID'er der ikke findes springes over uden at afbryde batch'en.
        """
        results = []
        for uuid in uuids:
            logger.info(f"Henter data for UUID: {uuid}")
            data = self.get_it_system_usage_by_uuid(uuid)
            if data:
                results.append(data)
            else:
                logger.warning(f"UUID {uuid} ikke fundet i KITOS - springer over")
        return results

    # --- Alle systemer (initial import) ---

    def get_all_system_usages(self, page_size: int = 250) -> List[Dict[str, Any]]:
        """Henter alle IT-systemanvendelser med paginering.

        Bruges til initial import: henter alle systemer den indloggede bruger
        har adgang til (dvs. MTM-organisationens systemer).
        """
        results = []
        page = 0
        while True:
            data = self._get(
                "/it-system-usages",
                {"page": page, "pageSize": page_size},
            )
            if not data:
                break
            results.extend(data)
            logger.info(f"Hentede side {page}: {len(data)} systemer (total: {len(results)})")
            if len(data) < page_size:
                break
            page += 1
        return results

    # --- DPR-opslag ---

    def get_dprs_for_system_usage(
        self, system_usage_uuid: str
    ) -> List[Dict[str, Any]]:
        """Henter alle databehandlingsregistreringer tilknyttet et system-usage UUID.

        Returnerer tom liste hvis ingen DPR'er findes.
        Filterparameter: systemUsageUuid (bekræftet via KITOS API V2).
        """
        try:
            data = self._get(
                "/data-processing-registrations",
                {"systemUsageUuid": system_usage_uuid, "page": 0, "pageSize": 100},
            )
            result = data or []
            logger.debug(
                f"Fandt {len(result)} DPR(er) for system-usage {system_usage_uuid}"
            )
            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            logger.error(
                f"HTTP fejl ved DPR-opslag for {system_usage_uuid}: {e}"
            )
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Fejl ved DPR-opslag for {system_usage_uuid}: {e}")
            raise
