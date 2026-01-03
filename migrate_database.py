#!/usr/bin/env python3

from models import SessionLocal
from sqlalchemy import text

def migrate_database():
    db = SessionLocal()
    
    try:
        # Add new columns to rooms table
        columns_to_add = [
            "ALTER TABLE tablelink_rooms ADD COLUMN room_type TEXT DEFAULT 'Standard'",
            "ALTER TABLE tablelink_rooms ADD COLUMN description TEXT",
            "ALTER TABLE tablelink_rooms ADD COLUMN price_per_night REAL DEFAULT 150.0",
            "ALTER TABLE tablelink_rooms ADD COLUMN max_guests INTEGER DEFAULT 2",
            "ALTER TABLE tablelink_rooms ADD COLUMN amenities TEXT",
            "ALTER TABLE tablelink_rooms ADD COLUMN image_url TEXT"
        ]
        
        for sql in columns_to_add:
            try:
                db.execute(text(sql))
                print(f"✅ Added column: {sql.split('ADD COLUMN')[1].split()[0]}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print(f"⚠️  Column already exists: {sql.split('ADD COLUMN')[1].split()[0]}")
                else:
                    print(f"❌ Error adding column: {e}")
        
        # Create bookings table
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS tablelink_room_bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER NOT NULL,
                    room_id INTEGER NOT NULL,
                    guest_name TEXT NOT NULL,
                    guest_email TEXT NOT NULL,
                    guest_phone TEXT,
                    check_in_date TEXT NOT NULL,
                    check_out_date TEXT NOT NULL,
                    total_nights INTEGER NOT NULL,
                    total_price REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    special_requests TEXT,
                    FOREIGN KEY (hotel_id) REFERENCES tablelink_hotels (id),
                    FOREIGN KEY (room_id) REFERENCES tablelink_rooms (id)
                )
            """))
            print("✅ Created bookings table")
        except Exception as e:
            print(f"⚠️  Bookings table: {e}")
        
        db.commit()
        print("\n🎉 Database migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_database()