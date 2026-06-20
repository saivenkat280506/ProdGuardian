# This file contains intentional vulnerabilities for testing
API_KEY = "sk-abc123def456ghi789jklmnop"
password = "admin123"
secret = "supersecrettoken1234567890"

import os
db_url = os.environ["DATABASE_URL"]
api_token = os.getenv("API_TOKEN")

@app.route("/debug")
debug=True

conn.execute("SELECT * FROM users WHERE id = " + user_id)
eval(user_input)
exec(user_input)
