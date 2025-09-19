from sqlalchemy.orm import Session
from models import Restaurant, User, Table, Waiter, MenuItem
from auth import get_password_hash
import re
from datetime import datetime, timedelta

def create_subdomain(restaurant_name: str, db: Session) -> str:
    """Generate a unique subdomain from restaurant name"""
    # Clean the name: lowercase, remove special chars, replace spaces with hyphens
    base_subdomain = re.sub(r'[^a-z0-9\s]', '', restaurant_name.lower())
    base_subdomain = re.sub(r'\s+', '-', base_subdomain.strip())
    
    # Ensure it's not empty and not too long
    if not base_subdomain:
        base_subdomain = "restaurant"
    base_subdomain = base_subdomain[:20]  # Limit length
    
    # Check for uniqueness
    subdomain = base_subdomain
    counter = 1
    while db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first():
        subdomain = f"{base_subdomain}-{counter}"
        counter += 1
    
    return subdomain

def create_new_restaurant(
    db: Session,
    restaurant_name: str,
    admin_email: str,
    admin_username: str,
    admin_password: str,
    table_count: int,
    plan_type: str = "trial",
    menu_file_content: bytes = None
) -> dict:
    """Create a new restaurant with all necessary setup"""
    try:
        # Generate unique subdomain
        subdomain = create_subdomain(restaurant_name, db)
        
        # Create restaurant with trial end date
        trial_ends_at = None
        if plan_type == "trial":
            trial_ends_at = datetime.utcnow() + timedelta(days=5)
        
        restaurant = Restaurant(
            name=restaurant_name,
            subdomain=subdomain,
            plan_type=plan_type,
            trial_ends_at=trial_ends_at,
            active=True,
            created_at=datetime.utcnow()
        )
        db.add(restaurant)
        db.flush()  # Get the ID
        
        restaurant_id = restaurant.id
        
        # Create admin user with provided credentials
        
        admin_user = User(
            username=admin_username,
            password_hash=get_password_hash(admin_password),
            role="admin",
            restaurant_id=restaurant_id
        )
        db.add(admin_user)
        
        # Create tables with proper codes
        table_codes = ['123', '456', '789', '321', '654', '987', '147', '258', '369', '741']
        for i in range(1, table_count + 1):
            code = table_codes[i-1] if i <= len(table_codes) else f"T{i:03d}"
            table = Table(
                table_number=i,
                code=code,
                status="free",
                restaurant_id=restaurant_id
            )
            db.add(table)
        
        # Create default waiter
        default_waiter = Waiter(
            name="Default Waiter",
            restaurant_id=restaurant_id
        )
        db.add(default_waiter)
        
        # Create default menu items if no file provided
        if not menu_file_content:
            default_items = [
                {"name": "Margherita Pizza", "ingredients": "Tomato, Mozzarella, Basil", "price": 12.50, "category": "Pizza"},
                {"name": "Caesar Salad", "ingredients": "Lettuce, Parmesan, Croutons, Caesar Dressing", "price": 8.90, "category": "Salad"},
                {"name": "Pasta Carbonara", "ingredients": "Pasta, Eggs, Bacon, Parmesan", "price": 14.00, "category": "Pasta"},
                {"name": "Tiramisu", "ingredients": "Mascarpone, Coffee, Ladyfingers", "price": 6.50, "category": "Dessert"}
            ]
            
            for item_data in default_items:
                menu_item = MenuItem(
                    name=item_data["name"],
                    ingredients=item_data["ingredients"],
                    price=item_data["price"],
                    category=item_data["category"],
                    active=True,
                    restaurant_id=restaurant_id
                )
                db.add(menu_item)
        else:
            # Process uploaded menu file
            try:
                from setup import process_excel_content
                process_excel_content(db, menu_file_content, restaurant_id)
            except Exception as e:
                print(f"Error processing menu file: {e}")
                # Fall back to default menu if file processing fails
                pass
        
        db.commit()
        
        return {
            "success": True,
            "restaurant_id": restaurant_id,
            "subdomain": subdomain,
            "login_url": f"http://localhost:8000/r/{subdomain}/business/login",
            "admin_username": admin_username,
            "admin_password": admin_password
        }
        
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }