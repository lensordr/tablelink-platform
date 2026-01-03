from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Hotel(Base):
    __tablename__ = "tablelink_hotels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    subdomain = Column(String(50), unique=True, nullable=False)
    plan_type = Column(String(20), default='trial')  # trial, basic, professional
    trial_ends_at = Column(DateTime)
    subscription_status = Column(String(20), default='trial')  # trial, active, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    # Hotel details for onboarding
    description = Column(String(1000))
    address = Column(String(500))
    phone = Column(String(20))
    email = Column(String(100))
    website = Column(String(200))
    header_image_url = Column(String(255))
    logo_url = Column(String(255))
    amenities = Column(String(1000))  # JSON string
    
    # Relationships
    users = relationship("User", back_populates="hotel")
    rooms = relationship("Room", back_populates="hotel")
    menu_items = relationship("MenuItem", back_populates="hotel")
    staff = relationship("Staff", back_populates="hotel")
    orders = relationship("Order", back_populates="hotel")
    analytics_records = relationship("AnalyticsRecord", back_populates="hotel")

class User(Base):
    __tablename__ = "tablelink_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    username = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='staff')  # 'admin', 'staff'
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    hotel = relationship("Hotel", back_populates="users")
    
    __table_args__ = (
        # Username should be unique per hotel
        {'sqlite_autoincrement': True}
    )

class Room(Base):
    __tablename__ = "tablelink_rooms"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    room_number = Column(Integer, nullable=False)
    code = Column(String(3), nullable=False)
    status = Column(String(10), default='available')  # 'available', 'occupied', 'booked'
    has_extra_order = Column(Boolean, default=False)
    checkout_requested = Column(Boolean, default=False)
    checkout_method = Column(String(10))  # 'cash' or 'card'
    tip_amount = Column(Float, default=0.0)
    
    # Room details for booking
    room_type = Column(String(50), default='Standard')
    description = Column(String(500))
    price_per_night = Column(Float, default=100.0)
    max_guests = Column(Integer, default=2)
    amenities = Column(String(500))  # JSON string
    image_url = Column(String(255))
    
    hotel = relationship("Hotel", back_populates="rooms")
    orders = relationship("Order", back_populates="room")
    bookings = relationship("RoomBooking", back_populates="room")

class MenuItem(Base):
    __tablename__ = "tablelink_menu_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    name = Column(String(100), nullable=False)
    ingredients = Column(String(500))
    price = Column(Float, nullable=False)
    category = Column(String(50), default='Food')
    active = Column(Boolean, default=True)
    
    hotel = relationship("Hotel", back_populates="menu_items")
    order_items = relationship("OrderItem", back_populates="menu_item")

class Staff(Base):
    __tablename__ = "tablelink_staff"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    
    hotel = relationship("Hotel", back_populates="staff")
    orders = relationship("Order", back_populates="staff_member")

class Order(Base):
    __tablename__ = "tablelink_orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('tablelink_rooms.id'))
    staff_id = Column(Integer, ForeignKey('tablelink_staff.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(10), default='active')  # 'active' or 'finished'
    tip_amount = Column(Float, default=0.0)
    
    hotel = relationship("Hotel", back_populates="orders")
    room = relationship("Room", back_populates="orders")
    staff_member = relationship("Staff", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")

class RoomBooking(Base):
    __tablename__ = "tablelink_room_bookings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('tablelink_rooms.id'), nullable=False)
    guest_name = Column(String(100), nullable=False)
    guest_email = Column(String(100), nullable=False)
    guest_phone = Column(String(20))
    check_in_date = Column(DateTime, nullable=False)
    check_out_date = Column(DateTime, nullable=False)
    total_nights = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String(20), default='pending')  # 'pending', 'confirmed', 'checked_in', 'completed', 'cancelled'
    created_at = Column(DateTime, default=datetime.utcnow)
    special_requests = Column(String(500))
    
    hotel = relationship("Hotel")
    room = relationship("Room", back_populates="bookings")

class OrderItem(Base):
    __tablename__ = "tablelink_order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('tablelink_orders.id'))
    product_id = Column(Integer, ForeignKey('tablelink_menu_items.id'))
    qty = Column(Integer, nullable=False)
    is_extra_item = Column(Boolean, default=False)
    is_new_extra = Column(Boolean, default=False)
    customizations = Column(String(1000))  # JSON string for ingredient modifications
    
    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")

class AnalyticsRecord(Base):
    __tablename__ = "tablelink_analytics_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey('tablelink_hotels.id'), nullable=False)
    checkout_date = Column(DateTime, nullable=False)
    room_number = Column(Integer, nullable=False)
    staff_id = Column(Integer, ForeignKey('tablelink_staff.id'))
    item_name = Column(String(100), nullable=False)
    item_category = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    tip_amount = Column(Float, default=0.0)
    
    hotel = relationship("Hotel", back_populates="analytics_records")
    staff_member = relationship("Staff")

# Database setup
import os

# Use shared PostgreSQL database with tablelink prefix
if os.getenv("DATABASE_SHARED_URL"):
    # Production (Heroku) - Use shared database
    DATABASE_URL = os.getenv("DATABASE_SHARED_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
elif os.getenv("DATABASE_URL"):
    # Fallback to regular DATABASE_URL
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
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
    if 'tablelink_analytics_records' not in inspector.get_table_names():
        AnalyticsRecord.__table__.create(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()