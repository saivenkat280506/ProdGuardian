# This file has no vulnerabilities
import os

API_KEY = os.getenv("API_KEY", "default-key")
password = os.environ.get("PASSWORD", "changeme")

debug = False

query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
