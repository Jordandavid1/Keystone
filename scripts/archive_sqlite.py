import json
import os
import shutil
import sqlite3
from pathlib import Path

def archive_keystone_db():
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    src_db = Path("keystone.db")
    dest_sqlite = artifacts_dir / "keystone-v1-final.sqlite"
    
    if src_db.exists():
        shutil.copy2(src_db, dest_sqlite)
        print(f"Archived sqlite to: {dest_sqlite}")
        
        con = sqlite3.connect(dest_sqlite)
        con.row_factory = sqlite3.Row
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cursor.fetchall()]
        
        export_data = {}
        for t in tables:
            rows = cursor.execute(f"SELECT * FROM {t}").fetchall()
            export_data[t] = [dict(r) for r in rows]
            
        dest_json = artifacts_dir / "keystone-v1-final-export.json"
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)
        print(f"Exported JSON with {len(export_data)} tables to {dest_json}")
    else:
        print("Warning: keystone.db not found")

if __name__ == "__main__":
    archive_keystone_db()
