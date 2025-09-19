from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Restaurant(Base):
    __tablename__ = "restaurants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    subdomain = Column(String(50), unique=True, nullable=False)
    plan_type = Column(String(20), default='trial')  # trial, basic, professional
    trial_ends_at = Column(DateTime)
    subscription_status = Column(String(20), default='trial')  # trial, active, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="restaurant")
    tables = relationship("Table", back_populates="restaurant")
    menu_items = relationship("MenuItem", back_populates="restaurant")
    waiters = relationship("Waiter", back_populates="restaurant")
    orders = relationship("Order", back_populates="restaurant")
    analytics_records = relationship("AnalyticsRecord", back_populates="restaurant")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    username = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='waiter')  # 'admin', 'waiter'
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    restaurant = relationship("Restaurant", back_populates="users")
    
    __table_args__ = (
        # Username should be unique per restaurant
        {'sqlite_autoincrement': True}
    )

class Table(Base):
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    table_number = Column(Integer, nullable=False)
    code = Column(String(3), nullable=False)
    status = Column(String(10), default='free')  # 'free' or 'occupied'
    has_extra_order = Column(Boolean, default=False)
    checkout_requested = Column(Boolean, default=False)
    checkout_method = Column(String(10))  # 'cash' or 'card'
    tip_amount = Column(Float, default=0.0)
    
    restaurant = relationship("Restaurant", back_populates="tables")
    orders = relationship("Order", back_populates="table")

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    name = Column(String(100), nullable=False)
    ingredients = Column(String(500))
    price = Column(Float, nullable=False)
    category = Column(String(50), default='Food')
    active = Column(Boolean, default=True)
    
    restaurant = relationship("Restaurant", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")

class Waiter(Base):
    __tablename__ = "waiters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    
    restaurant = relationship("Restaurant", back_populates="waiters")
    orders = relationship("Order", back_populates="waiter")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    table_id = Column(Integer, ForeignKey('tables.id'))
    waiter_id = Column(Integer, ForeignKey('waiters.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(10), default='active')  # 'active' or 'finished'
    tip_amount = Column(Float, default=0.0)
    
    restaurant = relationship("Restaurant", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    waiter = relationship("Waiter", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('menu_items.id'))
    qty = Column(Integer, nullable=False)
    is_extra_item = Column(Boolean, default=False)
    is_new_extra = Column(Boolean, default=False)
    customizations = Column(String(1000))  # JSON string for ingredient modifications
    
    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")

class AnalyticsRecord(Base):
    __tablename__ = "analytics_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'), nullable=False)
    checkout_date = Column(DateTime, nullable=False)
    table_number = Column(Integer, nullable=False)
    waiter_id = Column(Integer, ForeignKey('waiters.id'))
    item_name = Column(String(100), nullable=False)
    item_category = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    tip_amount = Column(Float, default=0.0)
    
    restaurant = relationship("Restaurant", back_populates="analytics_records")
    waiter = relationship("Waiter")

# Database setup
import os

# Use PostgreSQL in production, SQLite in development
if os.getenv("DATABASE_URL"):
    # Production (Railway)
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
else:
    # Development (local)
    DATABASE_URL = "sqlite:///./database.db"
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)
    
    # Create analytics table if it doesn't exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if 'analytics_records' not in inspector.get_table_names():
        AnalyticsRecord.__table__.create(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()