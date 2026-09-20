"""
database.py — Vision Guard Database and Data Management Module
SQLite-backed storage for monitoring history, incidents, alerts, evidence.
"""

import sqlite3
import os
import datetime
import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist. Called at startup."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = _conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS monitoring_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
        video_source    TEXT,
        person_count    INTEGER,
        density_score   REAL,
        density_level   TEXT,
        movement_speed  REAL,
        movement_level  TEXT,
        turbulence      REAL,
        risk_score      REAL,
        risk_level      TEXT
    );

    CREATE TABLE IF NOT EXISTS incidents (
        incident_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
        video_source    TEXT,
        people_count    INTEGER,
        density_score   REAL,
        movement_score  REAL,
        behavior_status TEXT,
        violence_status TEXT,
        weapon_status   TEXT,
        risk_score      REAL,
        risk_level      TEXT,
        alert_message   TEXT,
        evidence_path   TEXT
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
        level       TEXT,
        score       REAL,
        message     TEXT,
        action      TEXT
    );

    CREATE TABLE IF NOT EXISTS evidence (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
        filepath    TEXT,
        risk_level  TEXT,
        risk_score  REAL,
        people_count INTEGER
    );

    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE,
        password_hash TEXT,
        role          TEXT
    );
    """)

    from werkzeug.security import generate_password_hash
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.executemany("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", [
            ('admin', generate_password_hash('admin'), 'admin'),
            ('user', generate_password_hash('user'), 'user')
        ])

    conn.commit()
    conn.close()


def log_frame(video_source: str, person_count: int, density: dict, movement: dict, risk: dict):
    """Log a monitoring snapshot (every N seconds)."""
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO monitoring_history
            (video_source, person_count, density_score, density_level,
             movement_speed, movement_level, turbulence, risk_score, risk_level)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            video_source, person_count,
            density.get("density_score", 0),
            density.get("level", "LOW"),
            movement.get("speed", 0),
            movement.get("level", "NONE"),
            movement.get("turbulence", 0),
            risk.get("score", 0),
            risk.get("level", "SAFE"),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_frame error: {e}")


def log_incident(video_source: str, people_count: int, density: dict,
                 movement: dict, behavior: dict, violence: dict,
                 weapon: dict, risk: dict, alert_msg: str,
                 evidence_path: str = ""):
    """Log a high-risk incident."""
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO incidents
            (video_source, people_count, density_score, movement_score,
             behavior_status, violence_status, weapon_status,
             risk_score, risk_level, alert_message, evidence_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            video_source, people_count,
            density.get("density_score", 0),
            movement.get("score", 0),
            behavior.get("status", "NORMAL"),
            "Possible" if (violence or {}).get("detected") else "None",
            "Detected" if (weapon or {}).get("detected") else "None",
            risk.get("score", 0),
            risk.get("level", "SAFE"),
            alert_msg,
            evidence_path,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_incident error: {e}")


def log_alert(alert: dict):
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO alerts (level, score, message, action)
            VALUES (?,?,?,?)
        """, (alert.get("level"), alert.get("score"),
              alert.get("message"), alert.get("action")))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_alert error: {e}")


def log_evidence(filepath: str, risk_level: str, risk_score: float, people_count: int):
    try:
        conn = _conn()
        conn.execute("""
            INSERT INTO evidence (filepath, risk_level, risk_score, people_count)
            VALUES (?,?,?,?)
        """, (filepath, risk_level, risk_score, people_count))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] log_evidence error: {e}")


def get_recent_history(limit: int = 60, video_source: str = None) -> list:
    """Return recent monitoring history including video_source camera label."""
    try:
        conn = _conn()
        if video_source:
            rows = conn.execute("""
                SELECT timestamp, video_source, person_count, density_score, movement_speed,
                       risk_score, risk_level
                FROM monitoring_history
                WHERE video_source LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (f"%{video_source}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT timestamp, video_source, person_count, density_score, movement_speed,
                       risk_score, risk_level
                FROM monitoring_history
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]
    except Exception:
        return []


def get_recent_incidents(limit: int = 20, video_source: str = None) -> list:
    try:
        conn = _conn()
        if video_source:
            rows = conn.execute("""
                SELECT * FROM incidents WHERE video_source LIKE ? ORDER BY timestamp DESC LIMIT ?
            """, (f"%{video_source}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM incidents ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_recent_alerts(limit: int = 20) -> list:
    try:
        conn = _conn()
        rows = conn.execute("""
            SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_session_stats(video_source: str = None) -> dict:
    """Return aggregate statistics for the full database or for a specific camera source."""
    try:
        conn = _conn()
        if video_source:
            r = conn.execute("""
                SELECT COUNT(*) as frames,
                       MAX(person_count) as max_people,
                       AVG(person_count) as avg_people,
                       MAX(risk_score)   as max_risk,
                       AVG(risk_score)   as avg_risk
                FROM monitoring_history
                WHERE video_source LIKE ?
            """, (f"%{video_source}%",)).fetchone()
            incidents = conn.execute("SELECT COUNT(*) FROM incidents WHERE video_source LIKE ?", (f"%{video_source}%",)).fetchone()[0]
        else:
            r = conn.execute("""
                SELECT COUNT(*) as frames,
                       MAX(person_count) as max_people,
                       AVG(person_count) as avg_people,
                       MAX(risk_score)   as max_risk,
                       AVG(risk_score)   as avg_risk
                FROM monitoring_history
            """).fetchone()
            incidents = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        conn.close()
        return {
            "total_frames": r["frames"] or 0,
            "max_people": r["max_people"] or 0,
            "avg_people": round(r["avg_people"] or 0, 1),
            "max_risk": round(r["max_risk"] or 0, 1),
            "avg_risk": round(r["avg_risk"] or 0, 1),
            "total_incidents": incidents,
            "total_alerts": total_alerts,
        }
    except Exception as e:
        print(f"[DB] get_session_stats error: {e}")
        return {}


def clear_session_telemetry() -> bool:
    """Clear only frame telemetry for a fresh monitoring session without deleting evidence or incident logs."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM monitoring_history")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] clear_session_telemetry error: {e}")
        return False


def clear_database() -> bool:
    """Wipe all historical data and delete physical evidence files."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM monitoring_history")
        cur.execute("DELETE FROM incidents")
        cur.execute("DELETE FROM alerts")
        cur.execute("DELETE FROM evidence")
        conn.commit()
        conn.close()

        for folder in [config.EVIDENCE_IMG_DIR, config.EVIDENCE_VID_DIR]:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    path = os.path.join(folder, f)
                    if os.path.isfile(path):
                        try:
                            os.remove(path)
                        except Exception as ex:
                            print(f"[DB] Could not delete {path}: {ex}")

        return True
    except Exception as e:
        print(f"[DB] clear_database error: {e}")
        return False


def get_user(username: str):
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[DB] get_user error: {e}")
        return None
