#!/usr/bin/env python3

from models import SessionLocal
from sqlalchemy import text

def migrate_hotel_fields():
    db = SessionLocal()
    
    try:
        # Add new columns to hotels table
        hotel_columns = [
            "ALTER TABLE tablelink_hotels ADD COLUMN description TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN address TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN phone TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN email TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN website TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN header_image_url TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN logo_url TEXT",
            "ALTER TABLE tablelink_hotels ADD COLUMN amenities TEXT"
        ]
        
        for sql in hotel_columns:
            try:
                db.execute(text(sql))
                print(f"✅ Added hotel column: {sql.split('ADD COLUMN')[1].split()[0]}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print(f"⚠️  Hotel column already exists: {sql.split('ADD COLUMN')[1].split()[0]}")
                else:
                    print(f"❌ Error adding hotel column: {e}")
        
        db.commit()
        print("\n🎉 Hotel onboarding migration completed!")
        
        print(f"\n🔗 Onboarding Page:")
        print(f"  • Setup: http://localhost:8002/onboarding")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_hotel_fields()