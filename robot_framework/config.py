"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 3

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.aarhuskommune.local"
SMTP_PORT = 25
SCREENSHOT_SENDER = "robot@friend.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"

# KITOS sync
KITOS_CREDENTIAL = "KitosMTM"
SHAREPOINT_API_CREDENTIAL = "SharePointAPI"
SHAREPOINT_CERT_CREDENTIAL = "SharePointCert"
SHAREPOINT_URL_CONSTANT = "aktivt_systemejerskab_sharepoint"

# SharePoint listenavn
MTM_LIST = "a_s_MTM Systemer"
MTM_ACTIVE_FIELD = "AktivSync"
SHAREPOINT_SYNC_LIST = "a_s_IT-Systemer KITOS"


# Queue specific configs
# ----------------------

# The name of the job queue (if any)
QUEUE_NAME = None

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------
