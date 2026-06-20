import os
from flask import Flask, request

app = Flask(__name__)

API_KEY = "sk-abc123def456ghi789jklmnop"
password = "admin123"

@app.route("/debug")
def debug_info():
    return "debug info"

@app.route("/api/users")
def get_users():
    user_id = request.args.get("id")
    query = "SELECT * FROM users WHERE id = " + user_id
    return query

if __name__ == "__main__":
    app.run(debug=True)
