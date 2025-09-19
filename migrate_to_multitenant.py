from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base, Restaurant, User, Table, MenuItem, Waiter, Order, AnalyticsRecord
from datetime import datetime, timedelta
import os

# Database setup
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def migrate_to_multitenant():
    """Migrate existing single-tenant data to multi-tenant structure"""
    
    print("Starting multi-tenant migration...")
    
    # Create new tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if restaurants table exists and has data
        existing_restaurant = db.query(Restaurant).first()
        if existing_restaurant:
            print("Multi-tenant structure already exists!")
            return existing_restaurant.id
        
        # Create default restaurant
        default_restaurant = Restaurant(
            name="TableLink Demo Restaurant",
            subdomain="demo",
            plan_type="professional",  # Give full access for existing users
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
            subscription_status="trial"
        )
        db.add(default_restaurant)
        db.commit()
        db.refresh(default_restaurant)
        
        restaurant_id = default_restaurant.id
        print(f"Created default restaurant with ID: {restaurant_id}")
        
        # Migrate existing data by adding restaurant_id
        
        # Update users table
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN restaurant_id INTEGER"))
            db.execute(text(f"UPDATE users SET restaurant_id = {restaurant_id}"))
            print("Migrated users table")
        except Exception as e:
            print(f"Users migration: {e}")
        
        # Update tables table - need to handle primary key change
        try:
            # Add new columns
            db.execute(text("ALTER TABLE tables ADD COLUMN id INTEGER"))
            db.execute(text("ALTER TABLE tables ADD COLUMN restaurant_id INTEGER"))
            
            # Update with restaurant_id
            db.execute(text(f"UPDATE tables SET restaurant_id = {restaurant_id}"))
            
            # Create new table structure
            db.execute(text("""
                CREATE TABLE tables_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    restaurant_id INTEGER NOT NULL,
                    table_number INTEGER NOT NULL,
                    code VARCHAR(3) NOT NULL,
                    status VARCHAR(10) DEFAULT 'free',
                    has_extra_order BOOLEAN DEFAULT 0,
                    checkout_requested BOOLEAN DEFAULT 0,
                    checkout_method VARCHAR(10),
                    tip_amount FLOAT DEFAULT 0.0,
                    FOREIGN KEY(restaurant_id) REFERENCES restaurants (id)
                )
            """))
            
            # Copy data
            db.execute(text("""
                INSERT INTO tables_new (restaurant_id, table_number, code, status, has_extra_order, checkout_requested, checkout_method, tip_amount)
                SELECT restaurant_id, table_number, code, status, has_extra_order, checkout_requested, checkout_method, tip_amount
                FROM tables
            """))
            
            # Replace old table
            db.execute(text("DROP TABLE tables"))
            db.execute(text("ALTER TABLE tables_new RENAME TO tables"))
            
            print("Migrated tables table")
        except Exception as e:
            print(f"Tables migration: {e}")
        
        # Update menu_items table
        try:
            db.execute(text("ALTER TABLE menu_items ADD COLUMN restaurant_id INTEGER"))
            db.execute(text(f"UPDATE menu_items SET restaurant_id = {restaurant_id}"))
            print("Migrated menu_items table")
        except Exception as e:
            print(f"Menu items migration: {e}")
        
        # Update waiters table
        try:
            db.execute(text("ALTER TABLE waiters ADD COLUMN restaurant_id INTEGER"))
            db.execute(text(f"UPDATE waiters SET restaurant_id = {restaurant_id}"))
            print("Migrated waiters table")
        except Exception as e:
            print(f"Waiters migration: {e}")
        
        # Update orders table
        try:
            db.execute(text("ALTER TABLE orders ADD COLUMN restaurant_id INTEGER"))
            db.execute(text("ALTER TABLE orders ADD COLUMN table_id INTEGER"))
            
            db.execute(text(f"UPDATE orders SET restaurant_id = {restaurant_id}"))
            
            # Map table_number to table_id
            db.execute(text("""
                UPDATE orders 
                SET table_id = (
                    SELECT id FROM tables 
                    WHERE tables.table_number = orders.table_number 
                    AND tables.restaurant_id = orders.restaurant_id
                )
            """))
            
            print("Migrated orders table")
        except Exception as e:
            print(f"Orders migration: {e}")
        
        # Update analytics_records table
        try:
            db.execute(text("ALTER TABLE analytics_records ADD COLUMN restaurant_id INTEGER"))
            db.execute(text(f"UPDATE analytics_records SET restaurant_id = {restaurant_id}"))
            print("Migrated analytics_records table")
        except Exception as e:
            print(f"Analytics records migration: {e}")
        
        db.commit()
        print("Migration completed successfully!")
        return restaurant_id
        
    except Exception as e:
        print(f"Migration error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_to_multitenant()