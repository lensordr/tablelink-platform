#!/usr/bin/env python3
"""
Migration script to add table_count column to restaurants table
"""

import sqlite3
import os

def migrate_database():
    db_path = "database.db"
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet. Will be created on first run.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table_count column exists
        cursor.execute("PRAGMA table_info(restaurants)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'table_count' not in columns:
            print("Adding table_count column to restaurants table...")
            cursor.execute("ALTER TABLE restaurants ADD COLUMN table_count INTEGER DEFAULT 10")
            
            # Update existing restaurants with their actual table count
            cursor.execute("""
                UPDATE restaurants 
                SET table_count = (
                    SELECT COUNT(*) 
                    FROM tables 
                    WHERE tables.restaurant_id = restaurants.id
                )
                WHERE EXISTS (
                    SELECT 1 FROM tables WHERE tables.restaurant_id = restaurants.id
                )
            """)
            
            conn.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ table_count column already exists")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()