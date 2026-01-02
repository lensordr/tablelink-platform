from models import create_tables, get_db, Hotel, Room, Staff, User, MenuItem
from sqlalchemy.orm import Session
from datetime import datetime

def init_hotel_database():
    # Create all tables
    create_tables()
    
    db = next(get_db())
    
    try:
        # Check if hotel already exists
        existing_hotel = db.query(Hotel).first()
        if existing_hotel:
            print("Hotel database already initialized!")
            return
        
        # Create sample hotel
        hotel = Hotel(
            name="Luxury Grand Hotel",
            subdomain="demo",
            plan_type="trial",
            active=True,
            created_at=datetime.utcnow()
        )
        db.add(hotel)
        db.flush()  # Get the hotel ID
        
        # Create admin user
        from auth import get_password_hash
        admin_user = User(
            hotel_id=hotel.id,
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin",
            active=True
        )
        db.add(admin_user)
        
        # Create sample rooms
        rooms_data = [
            (101, "A1B"), (102, "C2D"), (103, "E3F"),
            (201, "G4H"), (202, "I5J"), (203, "K6L"),
            (301, "M7N"), (302, "O8P"), (303, "Q9R")
        ]
        
        for room_num, code in rooms_data:
            room = Room(
                hotel_id=hotel.id,
                room_number=room_num,
                code=code,
                status="available"
            )
            db.add(room)
        
        # Create sample staff
        staff_members = ["Alice Johnson", "Bob Smith", "Carol Davis"]
        for name in staff_members:
            staff = Staff(
                hotel_id=hotel.id,
                name=name,
                active=True
            )
            db.add(staff)
        
        # Create sample menu items
        menu_items = [
            ("Caesar Salad", "Fresh romaine, parmesan, croutons, caesar dressing", 18.50, "Appetizers"),
            ("Grilled Salmon", "Atlantic salmon, lemon butter, seasonal vegetables", 32.00, "Main Course"),
            ("Beef Tenderloin", "Prime cut, red wine reduction, mashed potatoes", 45.00, "Main Course"),
            ("Chocolate Cake", "Rich chocolate cake with vanilla ice cream", 12.00, "Desserts"),
            ("Club Sandwich", "Turkey, bacon, lettuce, tomato, fries", 22.00, "Light Meals"),
            ("Fresh Fruit Platter", "Seasonal fruits with honey yogurt", 16.00, "Healthy Options"),
            ("Champagne", "Dom Pérignon, bottle", 180.00, "Beverages"),
            ("Coffee", "Freshly brewed premium coffee", 6.00, "Beverages")
        ]
        
        for name, ingredients, price, category in menu_items:
            item = MenuItem(
                hotel_id=hotel.id,
                name=name,
                ingredients=ingredients,
                price=price,
                category=category,
                active=True
            )
            db.add(item)
        
        db.commit()
        print("✅ Hotel database initialized successfully!")
        print(f"🏨 Hotel: {hotel.name}")
        print(f"👤 Admin login: admin / admin123")
        print(f"🛏️ Rooms: {len(rooms_data)} rooms created")
        print(f"👨‍💼 Staff: {len(staff_members)} staff members")
        print(f"🍽️ Menu: {len(menu_items)} items")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error initializing database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_hotel_database()