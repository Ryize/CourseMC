"""YooKassa credentials loaded from the server environment."""

import os


SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")
SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
