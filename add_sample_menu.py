#!/usr/bin/env python3

from models import SessionLocal, MenuItem, Hotel
from sqlalchemy.orm import Session

def add_sample_menu():
    db = SessionLocal()
    
    try:
        # Get the first hotel (or create one if none exists)
        hotel = db.query(Hotel).first()
        if not hotel:
            hotel = Hotel(
                name="Demo Hotel",
                subdomain="demo"
            )
            db.add(hotel)
            db.commit()
            db.refresh(hotel)
        
        # Clear existing menu items for this hotel
        db.query(MenuItem).filter(MenuItem.hotel_id == hotel.id).delete()
        
        # Sample menu items
        menu_items = [
            # Appetizers
            {"name": "Caesar Salad", "ingredients": "Fresh romaine lettuce, parmesan cheese, croutons, caesar dressing", "price": 18.50, "category": "Appetizers"},
            {"name": "Truffle Arancini", "ingredients": "Risotto balls, truffle oil, parmesan, marinara sauce", "price": 22.00, "category": "Appetizers"},
            {"name": "Tuna Tartare", "ingredients": "Fresh tuna, avocado, sesame, soy glaze, wonton chips", "price": 26.00, "category": "Appetizers"},
            
            # Main Courses
            {"name": "Grilled Salmon", "ingredients": "Atlantic salmon, lemon butter, seasonal vegetables, quinoa", "price": 32.00, "category": "Main Courses"},
            {"name": "Ribeye Steak", "ingredients": "12oz ribeye, garlic mashed potatoes, asparagus, red wine jus", "price": 48.00, "category": "Main Courses"},
            {"name": "Lobster Ravioli", "ingredients": "Fresh lobster, ricotta, spinach, tomato cream sauce", "price": 38.00, "category": "Main Courses"},
            {"name": "Chicken Parmesan", "ingredients": "Breaded chicken breast, marinara, mozzarella, pasta", "price": 28.00, "category": "Main Courses"},
            
            # Desserts
            {"name": "Chocolate Lava Cake", "ingredients": "Warm chocolate cake, molten center, vanilla ice cream", "price": 14.00, "category": "Desserts"},
            {"name": "Tiramisu", "ingredients": "Mascarpone, ladyfingers, espresso, cocoa powder", "price": 12.00, "category": "Desserts"},
            
            # Beverages
            {"name": "House Wine", "ingredients": "Red or white wine selection", "price": 8.00, "category": "Beverages"},
            {"name": "Craft Beer", "ingredients": "Local brewery selection", "price": 6.00, "category": "Beverages"},
            {"name": "Fresh Juice", "ingredients": "Orange, apple, or cranberry", "price": 5.00, "category": "Beverages"},
            {"name": "Coffee", "ingredients": "Freshly brewed coffee", "price": 4.00, "category": "Beverages"},
        ]
        
        # Add menu items to database
        for item_data in menu_items:
            menu_item = MenuItem(
                hotel_id=hotel.id,
                **item_data
            )
            db.add(menu_item)
        
        db.commit()
        print(f"✅ Added {len(menu_items)} menu items to {hotel.name}")
        
        # Display added items
        print("\n📋 Menu Items Added:")
        for category in ["Appetizers", "Main Courses", "Desserts", "Beverages"]:
            items = [item for item in menu_items if item["category"] == category]
            if items:
                print(f"\n{category}:")
                for item in items:
                    print(f"  • {item['name']} - ${item['price']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_sample_menu()