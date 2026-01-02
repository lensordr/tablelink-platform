import os
os.environ["DATABASE_SHARED_URL"] = "postgres://ufbe17oj3evi1t:pd90fbab5faecba148dfd411edb230c2c158c8ab85b506c7f210504ded8a93de9@c5cnr847jq0fj3.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d7mdt8en454l5a"

from models import get_db, Hotel, Room, Staff, User
from sqlalchemy import text
from auth import get_password_hash

def add_hotel_data():
    db = next(get_db())
    
    try:
        # Check if hotel exists
        hotel = db.query(Hotel).first()
        if hotel:
            print("Hotel already exists!")
            return
        
        # Add hotel
        hotel = Hotel(
            name="Luxury Grand Hotel",
            subdomain="demo",
            plan_type="trial",
            active=True
        )
        db.add(hotel)
        db.flush()
        
        # Add admin user
        admin = User(
            hotel_id=hotel.id,
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin)
        
        # Add rooms
        rooms = [(101, "A1B"), (102, "C2D"), (201, "G4H")]
        for room_num, code in rooms:
            room = Room(
                hotel_id=hotel.id,
                room_number=room_num,
                code=code,
                status="available"
            )
            db.add(room)
        
        # Add staff
        staff = Staff(
            hotel_id=hotel.id,
            name="Alice Johnson"
        )
        db.add(staff)
        
        # Add menu items using raw SQL (since table has restaurant_id column)
        menu_items = [
            ("Caesar Salad", "Fresh romaine, parmesan", 18.50, "Appetizers"),
            ("Grilled Salmon", "Atlantic salmon, vegetables", 32.00, "Main Course"),
            ("Coffee", "Premium coffee", 6.00, "Beverages")
        ]
        
        for name, ingredients, price, category in menu_items:
            db.execute(text("""
                INSERT INTO tablelink_menu_items (restaurant_id, name, ingredients, price, category, active)
                VALUES (:hotel_id, :name, :ingredients, :price, :category, true)
            """), {
                "hotel_id": hotel.id,
                "name": name,
                "ingredients": ingredients,
                "price": price,
                "category": category
            })
        
        db.commit()
        print("✅ Hotel data added successfully!")
        print(f"Login: admin / admin123")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_hotel_data()