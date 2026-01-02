#!/usr/bin/env python3

from models import SessionLocal, Room, Hotel
from sqlalchemy.orm import Session

def add_sample_rooms():
    db = SessionLocal()
    
    try:
        # Get the first hotel
        hotel = db.query(Hotel).first()
        if not hotel:
            print("❌ No hotel found. Run add_sample_menu.py first.")
            return
        
        # Clear existing rooms
        db.query(Room).filter(Room.hotel_id == hotel.id).delete()
        
        # Add sample rooms
        rooms = [
            {"room_number": 101, "code": "A1B", "status": "available"},
            {"room_number": 102, "code": "C2D", "status": "occupied"},
            {"room_number": 201, "code": "E3F", "status": "available"},
            {"room_number": 202, "code": "G4H", "status": "occupied"},
            {"room_number": 301, "code": "I5J", "status": "available"},
        ]
        
        for room_data in rooms:
            room = Room(
                hotel_id=hotel.id,
                **room_data
            )
            db.add(room)
        
        db.commit()
        print(f"✅ Added {len(rooms)} rooms to {hotel.name}")
        
        print("\n🏨 Test Rooms Created:")
        for room in rooms:
            print(f"  • Room {room['room_number']} - Code: {room['code']} - Status: {room['status']}")
        
        print(f"\n🔗 Test URLs:")
        print(f"  • Room 101: http://localhost:5000/client/101")
        print(f"  • Room 102: http://localhost:5000/client/102") 
        print(f"  • Room 201: http://localhost:5000/client/201")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_sample_rooms()