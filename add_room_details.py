#!/usr/bin/env python3

from models import SessionLocal, Room, Hotel
from sqlalchemy.orm import Session
from sqlalchemy import text

def add_room_details():
    db = SessionLocal()
    
    try:
        # Get the first hotel
        hotel = db.query(Hotel).first()
        if not hotel:
            print("❌ No hotel found. Run add_sample_menu.py first.")
            return
        
        # Update existing rooms with booking details
        rooms_data = [
            {"room_number": 101, "room_type": "Standard", "description": "Comfortable room with city view", "price_per_night": 120.0, "max_guests": 2},
            {"room_number": 102, "room_type": "Deluxe", "description": "Spacious room with premium amenities", "price_per_night": 180.0, "max_guests": 3},
            {"room_number": 201, "room_type": "Suite", "description": "Luxury suite with separate living area", "price_per_night": 300.0, "max_guests": 4},
            {"room_number": 202, "room_type": "Standard", "description": "Modern room with garden view", "price_per_night": 130.0, "max_guests": 2},
            {"room_number": 301, "room_type": "Penthouse", "description": "Top floor suite with panoramic views", "price_per_night": 500.0, "max_guests": 6},
        ]
        
        for room_data in rooms_data:
            db.execute(text("""
                UPDATE tablelink_rooms 
                SET room_type = :room_type, 
                    description = :description, 
                    price_per_night = :price_per_night, 
                    max_guests = :max_guests,
                    amenities = 'WiFi, AC, TV, Mini Bar, Room Service'
                WHERE room_number = :room_number AND hotel_id = :hotel_id
            """), {
                "room_number": room_data["room_number"],
                "room_type": room_data["room_type"],
                "description": room_data["description"],
                "price_per_night": room_data["price_per_night"],
                "max_guests": room_data["max_guests"],
                "hotel_id": hotel.id
            })
        
        db.commit()
        print(f"✅ Updated {len(rooms_data)} rooms with booking details")
        
        print("\n🏨 Room Details Updated:")
        for room in rooms_data:
            print(f"  • Room {room['room_number']} - {room['room_type']} - ${room['price_per_night']}/night")
        
        print(f"\n🔗 Public Hotel Page:")
        print(f"  • Landing Page: http://localhost:8002/hotel/demo")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_room_details()