import sqlite3
import pandas as pd
from datetime import datetime

# Define the database name
DB_NAME = 'cuny_civic_network.db'


def get_connection():
    """Helper function to get a database connection."""
    return sqlite3.connect(DB_NAME)


def initialize_database():
    """Creates the necessary tables if they don't exist yet."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create the main Contacts table (imported from CSV)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS Network_Contacts
                   (
                       ID
                       TEXT
                       PRIMARY
                       KEY,
                       "Contact Name"
                       TEXT,
                       "Email/Phone/LinkedIn"
                       TEXT,
                       "URL (Overview Page)"
                       TEXT,
                       "Role/Title"
                       TEXT,
                       Campus
                       TEXT,
                       "Program/Org Affiliation"
                       TEXT,
                       Category
                       TEXT,
                       "Civic Domains"
                       TEXT,
                       "Capabilities / Expertise"
                       TEXT,
                       "Communities Served"
                       TEXT,
                       "Needs / Challenges"
                       TEXT,
                       "Oppurtunity Ideas"
                       TEXT,
                       "INI Alignments"
                       TEXT,
                       "Notes / Insights"
                       TEXT,
                       "Outreach Status"
                       TEXT,
                       "Last Email Sent"
                       TEXT
                   )
                   ''')

    # Create the Users table (for people using the app)
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
                       UNIQUE,
                       campus
                       TEXT,
                       role
                       TEXT,
                       focus
                       TEXT,
                       email
                       TEXT,
                       projects
                       TEXT,
                       created_at
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')

    # Create the Search Logs table (Analytics)
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
                       search_query
                       TEXT,
                       search_time
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

    # Create the Saved Collaborations table (Bookmarks)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS Saved_Collaborations
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       contact_id
                       TEXT,
                       saved_at
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
                   ),
                       FOREIGN KEY
                   (
                       contact_id
                   ) REFERENCES Network_Contacts
                   (
                       ID
                   )
                       )
                   ''')

    # --- SAFEGUARD: Add missing columns to older databases automatically ---
    try:
        cursor.execute("ALTER TABLE Users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass  # The column already exists, safely ignore

    try:
        cursor.execute("ALTER TABLE Users ADD COLUMN projects TEXT")
    except sqlite3.OperationalError:
        pass  # The column already exists, safely ignore

    conn.commit()
    conn.close()


def add_user(name, campus, role, focus):
    """Adds a new user to the database and returns their ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
                       INSERT INTO Users (name, campus, role, focus)
                       VALUES (?, ?, ?, ?)
                       ''', (name, campus, role, focus))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # If the user already exists, just get their ID
        cursor.execute('SELECT user_id FROM Users WHERE name = ?', (name,))
        user_id = cursor.fetchone()[0]

    conn.close()
    return user_id


def get_user_by_name(name):
    """Retrieves all 6 data points for an existing user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, campus, role, focus, email, projects FROM Users WHERE name = ?", (name,))
    user = cursor.fetchone()
    conn.close()
    return user


def update_user_profile(user_id, email, campus, role, focus, projects):
    """Updates an existing user's profile in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
                   UPDATE Users
                   SET email    = ?,
                       campus   = ?,
                       role     = ?,
                       focus    = ?,
                       projects = ?
                   WHERE user_id = ?
                   """, (email, campus, role, focus, projects, user_id))
    conn.commit()
    conn.close()


def log_search(user_id, query):
    """Logs a user's search query for analytics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
                   INSERT INTO Search_Logs (user_id, search_query)
                   VALUES (?, ?)
                   ''', (user_id, query))
    conn.commit()
    conn.close()


def save_collaboration(user_id, contact_id):
    """Saves a contact to a user's 'Interesting' list. Prevents duplicates."""
    conn = get_connection()
    cursor = conn.cursor()

    # First, check if they already saved this person so we don't get duplicates
    cursor.execute("SELECT id FROM Saved_Collaborations WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            "INSERT INTO Saved_Collaborations (user_id, contact_id) VALUES (?, ?)",
            (user_id, contact_id)
        )
        conn.commit()
    conn.close()


def get_saved_collaborations(user_id):
    """Retrieves all contacts a user has marked as interesting."""
    conn = get_connection()
    # We use a JOIN query to get the actual contact details, not just their IDs
    query = """
            SELECT nc.* \
            FROM Saved_Collaborations sc \
                     JOIN Network_Contacts nc ON sc.contact_id = nc.ID
            WHERE sc.user_id = ?
            ORDER BY sc.saved_at DESC \
            """
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df