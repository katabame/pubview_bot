import os
import sqlite3
from config import DB_PATH


def setup_database() -> None:
    """データベースの初期設定を行う"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cur: sqlite3.Cursor = con.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id INTEGER PRIMARY KEY,
            riot_puuid TEXT NOT NULL UNIQUE,
            game_name TEXT,
            tag_line TEXT,
            tier TEXT,
            rank TEXT,
            league_points INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sections (
            role_id INTEGER PRIMARY KEY,
            section_name TEXT NOT NULL UNIQUE,
            notification_channel_id INTEGER NOT NULL
        )
    ''')
    con.commit()
    con.close()
