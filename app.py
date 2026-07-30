import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Single route to load your app and all 21 screens
@app.route('/')
def index():
    return render_template('index.html')

# API route to save data submitted from any of your screens
@app.route('/api/save-log', methods=['POST'])
def save_log():
    data = request.json  # Receives JSON sent from your front-end JS
    user_input = data.get('log_data')

    if user_input:
        conn = get_db_connection()
        conn.execute('INSERT INTO logs (user_data) VALUES (?)', (user_input,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Log saved successfully!"})

    return jsonify({"status": "error", "message": "No data provided"}), 400

if __name__ == '__main__':
    app.run(debug=True)