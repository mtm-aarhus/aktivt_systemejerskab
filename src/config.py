import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "KITOS_EMAIL",
    "KITOS_PASSWORD",
    "SHAREPOINT_URL",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
]

KITOS_BASE_URL = os.getenv("KITOS_BASE_URL", "https://kitos.dk/api/v2")
KITOS_EMAIL = os.getenv("KITOS_EMAIL")
KITOS_PASSWORD = os.getenv("KITOS_PASSWORD")

SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

MTM_LIST = "a_s_MTM Systemer"
MTM_ACTIVE_FIELD = "AktivSync"
SHAREPOINT_SYNC_LIST = "a_s_IT-Systemer KITOS"


def validate_env():
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        print(f"FEJL: Manglende miljøvariabler: {', '.join(missing)}")
        print("Sæt dem i .env-filen eller med: setx VARIABELNAVN 'værdi'")
        sys.exit(1)


validate_env()
