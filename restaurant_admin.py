from sqlalchemy.orm import Session
from models import Restaurant, get_db
from datetime import datetime, timedelta
from crud import init_sample_data, create_user
import secrets
import string

def generate_subdomain(name: str) -> str:
    """Generate a clean subdomain from restaurant name"""
    # Remove special characters and spaces, convert to lowercase
    clean_name = ''.join(c.lower() for c in name if c.isalnum() or c in '-_')
    # Remove consecutive dashes/underscores
    while '--' in clean_name or '__' in clean_name or '-_' in clean_name or '_-' in clean_name:
        clean_name = clean_name.replace('--', '-').replace('__', '_').replace('-_', '-').replace('_-', '_')
    # Trim to reasonable length
    return clean_name[:20].strip('-_')

def create_restaurant(
    db: Session,
    name: str,
    subdomain: str = None,
    plan_type: str = "trial",
    admin_username: str = "admin",
    admin_password: str = None
) -> Restaurant:
    """Create a new restaurant with initial setup"""
    
    # Generate subdomain if not provided
    if not subdomain:
        subdomain = generate_subdomain(name)
    
    # Check if subdomain already exists
    existing = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
    if existing:
        # Add random suffix
        suffix = ''.join(secrets.choice(string.digits) for _ in range(3))
        subdomain = f"{subdomain}{suffix}"
    
    # Generate random password if not provided
    if not admin_password:
        admin_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    
    # Create restaurant
    restaurant = Restaurant(
        name=name,
        subdomain=subdomain,
        plan_type=plan_type,
        trial_ends_at=datetime.utcnow() + timedelta(days=5),  # 5-day trial
        subscription_status="trial"
    )
    
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    
    # Initialize sample data for the restaurant
    init_sample_data(db, restaurant.id)
    
    # Create admin user
    create_user(db, admin_username, admin_password, "admin", restaurant.id)
    
    print(f"Created restaurant '{name}' with subdomain '{subdomain}'")
    print(f"Admin login: {admin_username} / {admin_password}")
    print(f"Access URL: http://{subdomain}.tablelink.com (or http://localhost:8000/r/{subdomain})")
    
    return restaurant

def list_restaurants(db: Session):
    """List all restaurants"""
    restaurants = db.query(Restaurant).filter(Restaurant.active == True).all()
    
    print("\n=== RESTAURANTS ===")
    for r in restaurants:
        status = "🟢 Active" if r.subscription_status == "active" else "🟡 Trial" if r.subscription_status == "trial" else "🔴 Cancelled"
        trial_info = f" (expires {r.trial_ends_at.strftime('%Y-%m-%d')})" if r.trial_ends_at else ""
        print(f"ID: {r.id} | {r.name} | {r.subdomain} | {r.plan_type.upper()} | {status}{trial_info}")
    
    return restaurants

def update_restaurant_plan(db: Session, restaurant_id: int, plan_type: str, subscription_status: str = "active"):
    """Update restaurant plan and subscription status"""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        print(f"Restaurant {restaurant_id} not found")
        return None
    
    restaurant.plan_type = plan_type
    restaurant.subscription_status = subscription_status
    
    if subscription_status == "active":
        restaurant.trial_ends_at = None
    
    db.commit()
    db.refresh(restaurant)
    
    print(f"Updated {restaurant.name} to {plan_type} plan ({subscription_status})")
    return restaurant

if __name__ == "__main__":
    import sys
    
    db = next(get_db())
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python restaurant_admin.py list")
        print("  python restaurant_admin.py create 'Restaurant Name' [subdomain] [plan_type]")
        print("  python restaurant_admin.py upgrade <restaurant_id> <plan_type>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_restaurants(db)
    
    elif command == "create":
        if len(sys.argv) < 3:
            print("Please provide restaurant name")
            sys.exit(1)
        
        name = sys.argv[2]
        subdomain = sys.argv[3] if len(sys.argv) > 3 else None
        plan_type = sys.argv[4] if len(sys.argv) > 4 else "trial"
        
        create_restaurant(db, name, subdomain, plan_type)
    
    elif command == "upgrade":
        if len(sys.argv) < 4:
            print("Please provide restaurant_id and plan_type")
            sys.exit(1)
        
        restaurant_id = int(sys.argv[2])
        plan_type = sys.argv[3]
        
        update_restaurant_plan(db, restaurant_id, plan_type)
    
    else:
        print(f"Unknown command: {command}")
    
    db.close()