import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# tronaccs.market API
TRONACCS_API_URL = "https://system-api.tronaccs.market"

# Paths
SESSIONS_DIR = "sessions"
DB_PATH = "data.db"
