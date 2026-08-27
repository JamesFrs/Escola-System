import sqlite3
from config import DATABASE


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_db(sql, args=(), one=False):
    conn = get_db()
    cur = conn.execute(sql, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    lastid = cur.lastrowid
    conn.close()
    return lastid
