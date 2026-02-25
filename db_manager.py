import sqlite3
import os

DB_FILE = 'cuny_civic_network.db'


def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)


def initialize_database():
    """Creates the necessary tables if they don't exist yet."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: Users
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS Users
                   (
                       user_id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL,
                       campus
                       TEXT
                       NOT
                       NULL,
                       role
                       TEXT,
                       focus
                       TEXT,
                       status
                       TEXT
                       DEFAULT
                       'PENDING'
                   )
                   ''')

    # Table 2: Search_Logs
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS Search_Logs
                   (
                       log_id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       query
                       TEXT
                       NOT
                       NULL,
                       timestamp
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES Users
                   (
                       user_id
                   )
                       )
                   ''')

    conn.commit()
    conn.close()


def add_user(name, campus, role, focus):
    """Inserts a new user and returns their unique user_id."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
                   INSERT INTO Users (name, campus, role, focus)
                   VALUES (?, ?, ?, ?)
                   ''', (name, campus, role, focus))

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return user_id


def log_search(user_id, query):
    """Logs a search query tied to a specific user."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
                   INSERT INTO Search_Logs (user_id, query)
                   VALUES (?, ?)
                   ''', (user_id, query))

    conn.commit()
    conn.close()


def get_user_by_name(name):
    """Checks if a user already exists to prevent duplicates."""
    conn = get_connection()
    cursor = conn.cursor()

    # Query the database for this specific name
    cursor.execute("SELECT user_id, campus, role, focus FROM Users WHERE name = ?", (name,))
    user = cursor.fetchone()

    conn.close()
    return user  # Returns a tuple (id, campus, role, focus) if found, or None if not found

# When you run this file directly, it will build the database.
if __name__ == "__main__":
    initialize_database()
    print(f"✅ Database initialized successfully at {DB_FILE}")