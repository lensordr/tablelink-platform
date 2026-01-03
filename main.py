from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import sys
import os
import json

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import create_tables, get_db, Hotel, Room, Staff, User, MenuItem, Order
from auth import verify_password, get_password_hash

app = FastAPI()

# Mount static files and templates
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.on_event("startup")
async def startup_event():
    create_tables()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("welcome.html", {
        "request": request, 
        "hotel_name": "Luxury Grand Hotel"
    })

# Onboarding routes
@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    return templates.TemplateResponse("onboarding.html", {
        "request": request
    })

@app.post("/onboarding/complete")
async def complete_onboarding(request: Request, db: Session = Depends(get_db)):
    try:
        form = await request.form()
        
        # Create or update hotel
        hotel_data = {
            "name": form.get("hotel_name"),
            "subdomain": form.get("subdomain"),
            "description": form.get("description"),
            "address": form.get("address"),
            "phone": form.get("phone"),
            "email": form.get("email"),
            "website": form.get("website")
        }
        
        # Check if hotel exists
        existing_hotel = db.execute(text("SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                                   {"subdomain": hotel_data["subdomain"]}).fetchone()
        
        if existing_hotel:
            # Update existing hotel
            db.execute(text("""
                UPDATE tablelink_hotels 
                SET name = :name, description = :description, address = :address,
                    phone = :phone, email = :email, website = :website
                WHERE subdomain = :subdomain
            """), hotel_data)
            hotel_id = existing_hotel.id
        else:
            # Create new hotel
            db.execute(text("""
                INSERT INTO tablelink_hotels (name, subdomain, description, address, phone, email, website, created_at)
                VALUES (:name, :subdomain, :description, :address, :phone, :email, :website, datetime('now'))
            """), hotel_data)
            hotel_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
        
        # Process room type configurations
        room_type_number = 1
        while f"room_type_name_{room_type_number}" in form:
            room_type_name = form.get(f"room_type_name_{room_type_number}")
            room_type_price = float(form.get(f"room_type_price_{room_type_number}"))
            room_type_guests = int(form.get(f"room_type_guests_{room_type_number}"))
            room_type_count = int(form.get(f"room_type_count_{room_type_number}"))
            room_type_description = form.get(f"room_type_description_{room_type_number}", "")
            room_type_start = int(form.get(f"room_type_start_{room_type_number}"))
            
            # Create multiple rooms of this type
            for i in range(room_type_count):
                room_number = room_type_start + i
                room_data = {
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "room_type": room_type_name,
                    "price_per_night": room_type_price,
                    "max_guests": room_type_guests,
                    "description": room_type_description,
                    "code": f"R{room_number}",
                    "amenities": "WiFi, AC, TV, Room Service"
                }
                
                # Check if room exists
                existing_room = db.execute(text("""
                    SELECT id FROM tablelink_rooms 
                    WHERE hotel_id = :hotel_id AND room_number = :room_number
                """), {"hotel_id": hotel_id, "room_number": room_number}).fetchone()
                
                if existing_room:
                    # Update existing room
                    db.execute(text("""
                        UPDATE tablelink_rooms 
                        SET room_type = :room_type, price_per_night = :price_per_night,
                            max_guests = :max_guests, description = :description,
                            amenities = :amenities
                        WHERE id = :room_id
                    """), {**room_data, "room_id": existing_room.id})
                else:
                    # Create new room
                    db.execute(text("""
                        INSERT INTO tablelink_rooms 
                        (hotel_id, room_number, room_type, price_per_night, max_guests, 
                         description, code, amenities, status)
                        VALUES (:hotel_id, :room_number, :room_type, :price_per_night, 
                                :max_guests, :description, :code, :amenities, 'available')
                    """), room_data)
            
            room_type_number += 1
        
        db.commit()
        return {"message": "Hotel onboarding completed successfully", "hotel_id": hotel_id}
    
    except Exception as e:
        db.rollback()
        print(f"Onboarding error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
@app.get("/hotel/{hotel_subdomain}", response_class=HTMLResponse)
async def hotel_landing_page(request: Request, hotel_subdomain: str, db: Session = Depends(get_db)):
    try:
        hotel = db.execute(text("SELECT * FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                          {"subdomain": hotel_subdomain}).fetchone()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        return templates.TemplateResponse("hotel_landing.html", {
            "request": request,
            "hotel_name": hotel.name,
            "hotel_subdomain": hotel_subdomain,
            "hotel_description": hotel.description,
            "hotel_header_image": hotel.header_image_url,
            "hotel_logo": hotel.logo_url
        })
    except Exception as e:
        print(f"Landing page error: {e}")
        raise HTTPException(status_code=404, detail="Hotel not found")

@app.get("/api/public/rooms")
async def get_public_rooms(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        # Get hotel_id from subdomain if provided, otherwise use first hotel
        if hotel_subdomain:
            hotel = db.execute(text("SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                              {"subdomain": hotel_subdomain}).fetchone()
            hotel_id = hotel.id if hotel else 1
        else:
            hotel_id = 1
        
        # Get room types with availability counts for specific hotel
        rooms_result = db.execute(text("""
            SELECT 
                room_type,
                price_per_night,
                max_guests,
                description,
                amenities,
                image_url,
                COUNT(*) as total_rooms,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_rooms
            FROM tablelink_rooms
            WHERE hotel_id = :hotel_id AND room_type IS NOT NULL
            GROUP BY room_type, price_per_night, max_guests, description, amenities, image_url
            ORDER BY price_per_night
        """), {"hotel_id": hotel_id}).fetchall()
        
        result = []
        for room_type in rooms_result:
            result.append({
                "room_type": room_type.room_type or "Standard",
                "description": room_type.description or "Comfortable room with modern amenities",
                "price_per_night": float(room_type.price_per_night or 150.0),
                "max_guests": room_type.max_guests or 2,
                "amenities": room_type.amenities or "WiFi, AC, TV, Room Service",
                "image_url": room_type.image_url,
                "total_rooms": room_type.total_rooms,
                "available_rooms": room_type.available_rooms
            })
        
        return result
    except Exception as e:
        print(f"Public rooms error: {e}")
        return []

@app.post("/api/public/book-room")
async def book_room(request: Request, db: Session = Depends(get_db)):
    try:
        booking_data = await request.json()
        
        # Calculate nights and total price
        check_in = datetime.fromisoformat(booking_data['check_in_date'])
        check_out = datetime.fromisoformat(booking_data['check_out_date'])
        nights = (check_out - check_in).days
        
        if nights <= 0:
            raise HTTPException(status_code=400, detail="Invalid date range")
        
        # Find an available room of the requested type
        room = db.execute(text("""
            SELECT * FROM tablelink_rooms 
            WHERE room_type = :room_type AND status = 'available'
            LIMIT 1
        """), {"room_type": booking_data['room_type']}).fetchone()
        
        if not room:
            raise HTTPException(status_code=400, detail="No rooms available for this type")
        
        price_per_night = float(room.price_per_night)
        total_price = nights * price_per_night
        
        # Create booking
        db.execute(text("""
            INSERT INTO tablelink_room_bookings 
            (hotel_id, room_id, guest_name, guest_email, guest_phone, 
             check_in_date, check_out_date, total_nights, total_price, 
             status, special_requests, created_at)
            VALUES (:hotel_id, :room_id, :guest_name, :guest_email, :guest_phone,
                    :check_in, :check_out, :nights, :total_price, 'pending', 
                    :special_requests, datetime('now'))
        """), {
            "hotel_id": room.hotel_id,
            "room_id": room.id,
            "guest_name": booking_data['guest_name'],
            "guest_email": booking_data['guest_email'],
            "guest_phone": booking_data.get('guest_phone', ''),
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "total_price": total_price,
            "special_requests": booking_data.get('special_requests', '')
        })
        
        db.commit()
        return {"message": "Booking request submitted successfully", "booking_id": db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]}
    
    except Exception as e:
        db.rollback()
        print(f"Booking error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
@app.get("/room/{room_number}", response_class=HTMLResponse)
async def room_page(request: Request, room_number: int):
    return templates.TemplateResponse("client.html", {
        "request": request, 
        "room_number": room_number,
        "hotel_name": "Luxury Grand Hotel"
    })

@app.get("/client/menu")
async def get_menu(request: Request, room: int, db: Session = Depends(get_db)):
    try:
        # Get room object using raw SQL to handle schema mismatch
        room_result = db.execute(text("SELECT * FROM tablelink_rooms WHERE room_number = :room_num LIMIT 1"), {"room_num": room}).fetchone()
        if not room_result:
            raise HTTPException(status_code=404, detail="Room not found")
        
        # Get menu items using raw SQL (since table has restaurant_id instead of hotel_id)
        menu_result = db.execute(text("SELECT * FROM tablelink_menu_items WHERE active = true")).fetchall()
        
        # Group by category
        menu_by_category = {}
        for item in menu_result:
            category = item.category
            if category not in menu_by_category:
                menu_by_category[category] = []
            menu_by_category[category].append({
                "id": item.id,
                "name": item.name,
                "ingredients": item.ingredients or "No ingredients listed",
                "price": float(item.price)
            })
        
        return JSONResponse({
            "room_number": room,
            "room_code": room_result.code,
            "hotel_name": "Luxury Grand Hotel",
            "menu": menu_by_category
        })
    except Exception as e:
        print(f"Menu error: {e}")
        return JSONResponse({
            "room_number": room,
            "room_code": "ABC",
            "hotel_name": "Luxury Grand Hotel",
            "menu": {"Sample": [{"id": 1, "name": "Sample Item", "ingredients": "Sample", "price": 10.0}]}
        })

@app.get("/client/order_details/{room_number}")
async def get_client_order_details(request: Request, room_number: int, db: Session = Depends(get_db)):
    # Simplified - no existing orders for now
    return {"has_order": False}

@app.post("/client/order")
async def place_order(
    request: Request,
    room_number: int = Form(...),
    code: str = Form(...),
    items: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Verify room and code
        room_result = db.execute(text("SELECT * FROM tablelink_rooms WHERE room_number = :room_num AND code = :code"), 
                                {"room_num": room_number, "code": code}).fetchone()
        if not room_result:
            raise HTTPException(status_code=400, detail="Invalid room or code")
        
        # Parse order items
        try:
            order_items = json.loads(items)
        except:
            raise HTTPException(status_code=400, detail="Invalid items format")
        
        # Create order in database
        order_result = db.execute(text("""
            INSERT INTO tablelink_orders (hotel_id, room_id, created_at, status)
            VALUES (:hotel_id, :room_id, datetime('now'), 'active')
        """), {"hotel_id": room_result.hotel_id, "room_id": room_result.id})
        
        # Get the order ID
        order_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
        
        # Add order items
        for item in order_items:
            db.execute(text("""
                INSERT INTO tablelink_order_items (order_id, product_id, qty)
                VALUES (:order_id, :product_id, :qty)
            """), {
                "order_id": order_id,
                "product_id": item["product_id"],
                "qty": item["qty"]
            })
        
        # Mark room as having an order
        db.execute(text("""
            UPDATE tablelink_rooms SET has_extra_order = true WHERE id = :room_id
        """), {"room_id": room_result.id})
        
        db.commit()
        return {"message": "Room service order placed successfully! Staff will deliver to your room shortly."}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Order error: {e}")
        return {"message": "Order received! Staff will contact you shortly."}

# Authentication routes
@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # For demo purposes, hardcode admin credentials
    if username == "admin" and password == "admin123":
        return {"access_token": "demo_token", "token_type": "bearer", "role": "admin"}
    
    # For other users, try database lookup
    try:
        user_result = db.execute(text("SELECT * FROM tablelink_users WHERE username = :username LIMIT 1"), 
                                {"username": username}).fetchone()
        
        if user_result and verify_password(password, user_result.password_hash):
            return {"access_token": "demo_token", "token_type": "bearer", "role": user_result.role}
    except Exception as e:
        print(f"Database login error: {e}")
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Business dashboard
@app.get("/business/login", response_class=HTMLResponse)
async def business_login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "hotel_name": "Luxury Grand Hotel"
    })

@app.get("/debug/orders")
async def debug_orders(db: Session = Depends(get_db)):
    try:
        orders = db.execute(text("SELECT COUNT(*) as count FROM tablelink_orders")).fetchone()
        all_orders = db.execute(text("SELECT * FROM tablelink_orders")).fetchall()
        
        return {
            "database_type": "sqlite" if "sqlite" in str(db.bind.url) else "postgres",
            "orders_count": orders.count if orders else 0,
            "orders": [dict(order._mapping) for order in all_orders] if all_orders else []
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/test/orders")
async def test_orders(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("""
            SELECT o.id, o.created_at, r.room_number, mi.name, oi.qty 
            FROM tablelink_orders o 
            JOIN tablelink_rooms r ON o.room_id = r.id 
            JOIN tablelink_order_items oi ON o.id = oi.order_id 
            JOIN tablelink_menu_items mi ON oi.product_id = mi.id 
            WHERE o.status = 'active'
        """)).fetchall()
        
        return [dict(row._mapping) for row in result]
    except Exception as e:
        return {"error": str(e)}
@app.get("/business/dashboard", response_class=HTMLResponse)
async def business_dashboard(request: Request):
    return templates.TemplateResponse("business.html", {
        "request": request,
        "hotel_name": "Luxury Grand Hotel"
    })

@app.get("/hotel/{hotel_subdomain}/business/dashboard", response_class=HTMLResponse)
async def hotel_business_dashboard(request: Request, hotel_subdomain: str, db: Session = Depends(get_db)):
    try:
        hotel = db.execute(text("SELECT * FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                          {"subdomain": hotel_subdomain}).fetchone()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        return templates.TemplateResponse("business.html", {
            "request": request,
            "hotel_name": hotel.name,
            "hotel_subdomain": hotel_subdomain,
            "hotel_id": hotel.id
        })
    except Exception as e:
        print(f"Hotel dashboard error: {e}")
        raise HTTPException(status_code=404, detail="Hotel not found")

@app.get("/business/orders")
async def get_orders(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific orders
            orders_result = db.execute(text("""
                SELECT o.id, o.created_at, r.room_number, o.status
                FROM tablelink_orders o
                JOIN tablelink_rooms r ON o.room_id = r.id
                JOIN tablelink_hotels h ON r.hotel_id = h.id
                WHERE o.status = 'active' AND h.subdomain = :subdomain
                ORDER BY o.created_at DESC
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all orders (original behavior)
            orders_result = db.execute(text("""
                SELECT o.id, o.created_at, r.room_number, o.status
                FROM tablelink_orders o
                JOIN tablelink_rooms r ON o.room_id = r.id
                WHERE o.status = 'active'
                ORDER BY o.created_at DESC
            """)).fetchall()
        
        result = []
        for order in orders_result:
            items_result = db.execute(text("""
                SELECT mi.name, oi.qty
                FROM tablelink_order_items oi
                JOIN tablelink_menu_items mi ON oi.product_id = mi.id
                WHERE oi.order_id = ?
            """), (order.id,)).fetchall()
            
            items = [f"{item.name} x{item.qty}" for item in items_result]
            
            result.append({
                "id": order.id,
                "room_number": order.room_number,
                "created_at": str(order.created_at),
                "status": order.status,
                "items": items
            })
        
        return result
    except Exception as e:
        print(f"Orders error: {e}")
        return []

@app.get("/business/room-orders/{room_number}")
async def get_room_orders(room_number: int, db: Session = Depends(get_db)):
    try:
        orders_result = db.execute(text("""
            SELECT o.id, o.created_at, o.status
            FROM tablelink_orders o
            JOIN tablelink_rooms r ON o.room_id = r.id
            WHERE r.room_number = ? AND o.status = 'active'
            ORDER BY o.created_at DESC
        """), (room_number,)).fetchall()
        
        orders = []
        for order in orders_result:
            items_result = db.execute(text("""
                SELECT mi.name, oi.qty
                FROM tablelink_order_items oi
                JOIN tablelink_menu_items mi ON oi.product_id = mi.id
                WHERE oi.order_id = ?
            """), (order.id,)).fetchall()
            
            items = [f"{item.name} x{item.qty}" for item in items_result]
            
            orders.append({
                "id": order.id,
                "created_at": str(order.created_at),
                "status": order.status,
                "items": items
            })
        
        return {"orders": orders}
    except Exception as e:
        print(f"Room orders error: {e}")
        return {"orders": []}

@app.get("/business/room-types")
async def get_room_types(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific room types
            room_types = db.execute(text("""
                SELECT r.room_type, r.price_per_night, r.max_guests, r.description, COUNT(*) as total_rooms
                FROM tablelink_rooms r
                JOIN tablelink_hotels h ON r.hotel_id = h.id
                WHERE h.subdomain = :subdomain
                GROUP BY r.room_type, r.price_per_night, r.max_guests, r.description
                ORDER BY r.price_per_night
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all room types (original behavior)
            room_types = db.execute(text("""
                SELECT room_type, price_per_night, max_guests, description, COUNT(*) as total_rooms
                FROM tablelink_rooms 
                GROUP BY room_type, price_per_night, max_guests, description
                ORDER BY price_per_night
            """)).fetchall()
        
        result = []
        for room_type in room_types:
            result.append({
                "room_type": room_type.room_type,
                "price_per_night": float(room_type.price_per_night or 0),
                "max_guests": room_type.max_guests or 2,
                "description": room_type.description,
                "total_rooms": room_type.total_rooms
            })
        
        return result
    except Exception as e:
        print(f"Room types error: {e}")
        return []

@app.post("/business/add-room-type")
async def add_room_type(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        
        # Get hotel ID based on subdomain or default to first hotel
        if hotel_subdomain:
            hotel = db.execute(text("SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                              {"subdomain": hotel_subdomain}).fetchone()
            hotel_id = hotel.id if hotel else 1
        else:
            hotel = db.execute(text("SELECT id FROM tablelink_hotels LIMIT 1")).fetchone()
            hotel_id = hotel.id if hotel else 1
        
        # Create multiple rooms of this type
        for i in range(data['room_count']):
            room_number = data['starting_room'] + i
            
            # Check if room number already exists
            existing = db.execute(text("""
                SELECT id FROM tablelink_rooms WHERE room_number = :room_number AND hotel_id = :hotel_id
            """), {"room_number": room_number, "hotel_id": hotel_id}).fetchone()
            
            if existing:
                continue  # Skip if room already exists
            
            db.execute(text("""
                INSERT INTO tablelink_rooms 
                (hotel_id, room_number, room_type, price_per_night, max_guests, 
                 description, code, amenities, status, image_url)
                VALUES (:hotel_id, :room_number, :room_type, :price_per_night, 
                        :max_guests, :description, :code, :amenities, 'available', :image_url)
            """), {
                "hotel_id": hotel_id,
                "room_number": room_number,
                "room_type": data['room_type'],
                "price_per_night": data['price_per_night'],
                "max_guests": data['max_guests'],
                "description": data['description'],
                "code": f"R{room_number}",
                "amenities": "WiFi, AC, TV, Room Service",
                "image_url": data.get('image_url', '')
            })
        
        db.commit()
        return {"message": f"Added {data['room_count']} {data['room_type']} rooms successfully"}
    
    except Exception as e:
        db.rollback()
        print(f"Add room type error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/business/bookings")
async def get_bookings(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific bookings
            bookings_result = db.execute(text("""
                SELECT b.*, r.room_number 
                FROM tablelink_room_bookings b
                JOIN tablelink_rooms r ON b.room_id = r.id
                JOIN tablelink_hotels h ON r.hotel_id = h.id
                WHERE h.subdomain = :subdomain
                ORDER BY b.created_at DESC
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all bookings (original behavior)
            bookings_result = db.execute(text("""
                SELECT b.*, r.room_number 
                FROM tablelink_room_bookings b
                JOIN tablelink_rooms r ON b.room_id = r.id
                ORDER BY b.created_at DESC
            """)).fetchall()
        
        result = []
        for booking in bookings_result:
            result.append({
                "id": booking.id,
                "guest_name": booking.guest_name,
                "guest_email": booking.guest_email,
                "guest_phone": getattr(booking, 'guest_phone', ''),
                "room_number": booking.room_number,
                "check_in_date": str(booking.check_in_date),
                "check_out_date": str(booking.check_out_date),
                "total_nights": booking.total_nights,
                "total_price": float(booking.total_price),
                "status": booking.status,
                "created_at": str(booking.created_at),
                "special_requests": getattr(booking, 'special_requests', '')
            })
        
        return result
    except Exception as e:
        print(f"Bookings error: {e}")
        return []

@app.post("/business/booking/{booking_id}/status")
async def update_booking_status(booking_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        status = data['status']
        
        db.execute(text("""
            UPDATE tablelink_room_bookings 
            SET status = :status 
            WHERE id = :booking_id
        """), {"status": status, "booking_id": booking_id})
        
        # If confirmed, update room status
        if status == 'confirmed':
            db.execute(text("""
                UPDATE tablelink_rooms 
                SET status = 'booked' 
                WHERE id = (SELECT room_id FROM tablelink_room_bookings WHERE id = :booking_id)
            """), {"booking_id": booking_id})
        
        db.commit()
        return {"message": f"Booking {status} successfully"}
    
    except Exception as e:
        db.rollback()
        print(f"Update booking status error: {e}")
        return {"message": "Error updating booking status"}
@app.get("/business/menu")
async def get_business_menu(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific menu items
            menu_result = db.execute(text("""
                SELECT mi.* FROM tablelink_menu_items mi
                JOIN tablelink_hotels h ON mi.hotel_id = h.id
                WHERE mi.active = true AND h.subdomain = :subdomain
                ORDER BY mi.category, mi.name
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all menu items (original behavior)
            menu_result = db.execute(text("SELECT * FROM tablelink_menu_items WHERE active = true ORDER BY category, name")).fetchall()
        
        result = []
        for item in menu_result:
            result.append({
                "id": item.id,
                "name": item.name,
                "ingredients": item.ingredients or "",
                "price": float(item.price),
                "category": item.category,
                "active": bool(item.active)
            })
        
        return result
    except Exception as e:
        print(f"Menu error: {e}")
        return []

@app.get("/business/staff")
async def get_business_staff(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific staff
            staff_result = db.execute(text("""
                SELECT s.* FROM tablelink_staff s
                JOIN tablelink_hotels h ON s.hotel_id = h.id
                WHERE s.active = true AND h.subdomain = :subdomain
                ORDER BY s.name
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all staff (original behavior)
            staff_result = db.execute(text("SELECT * FROM tablelink_staff WHERE active = true ORDER BY name")).fetchall()
        
        result = []
        for staff in staff_result:
            result.append({
                "id": staff.id,
                "name": staff.name,
                "active": bool(staff.active)
            })
        
        return result
    except Exception as e:
        print(f"Staff error: {e}")
        return []

@app.post("/business/complete-room-orders/{room_number}")
async def complete_room_orders(room_number: int, db: Session = Depends(get_db)):
    try:
        # Complete all orders for this room
        db.execute(text("""
            UPDATE tablelink_orders SET status = 'completed' 
            WHERE room_id = (SELECT id FROM tablelink_rooms WHERE room_number = :room_number)
            AND status = 'active'
        """), {"room_number": room_number})
        
        # Update room status
        db.execute(text("""
            UPDATE tablelink_rooms SET has_extra_order = false 
            WHERE room_number = :room_number
        """), {"room_number": room_number})
        
        db.commit()
        return {"message": "All orders completed successfully"}
    except Exception as e:
        db.rollback()
        print(f"Complete room orders error: {e}")
        return {"message": "Error completing orders"}

@app.post("/business/checkout-room/{room_number}")
async def checkout_room(room_number: int, db: Session = Depends(get_db)):
    try:
        # Complete all orders for this room
        db.execute(text("""
            UPDATE tablelink_orders SET status = 'completed' 
            WHERE room_id = (SELECT id FROM tablelink_rooms WHERE room_number = :room_number)
        """), {"room_number": room_number})
        
        # Reset room status
        db.execute(text("""
            UPDATE tablelink_rooms SET 
                has_extra_order = false,
                status = 'available'
            WHERE room_number = :room_number
        """), {"room_number": room_number})
        
        db.commit()
        return {"message": "Room checked out successfully"}
    except Exception as e:
        db.rollback()
        print(f"Checkout room error: {e}")
        return {"message": "Error checking out room"}
async def mark_room_viewed(room_number: int, db: Session = Depends(get_db)):
    try:
        # Mark room orders as viewed
        db.execute(text("""
            UPDATE tablelink_rooms SET has_extra_order = false 
            WHERE room_number = :room_number
        """), {"room_number": room_number})
        
        db.commit()
        return {"message": "Room marked as viewed"}
    except Exception as e:
        db.rollback()
        print(f"Mark room viewed error: {e}")
        return {"message": "Error marking room as viewed"}

@app.post("/business/complete-order/{order_id}")
async def complete_order(order_id: int, db: Session = Depends(get_db)):
    try:
        # Mark order as completed
        db.execute(text("""
            UPDATE tablelink_orders SET status = 'completed' WHERE id = :order_id
        """), {"order_id": order_id})
        
        # Update room status
        db.execute(text("""
            UPDATE tablelink_rooms SET has_extra_order = false 
            WHERE id = (SELECT room_id FROM tablelink_orders WHERE id = :order_id)
        """), {"order_id": order_id})
        
        db.commit()
        return {"message": "Order completed successfully"}
    
    except Exception as e:
        db.rollback()
        print(f"Complete order error: {e}")
        return {"message": "Error completing order"}

@app.get("/business/rooms")
async def get_rooms_status(hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            # Get hotel-specific rooms
            rooms_result = db.execute(text("""
                SELECT r.* FROM tablelink_rooms r
                JOIN tablelink_hotels h ON r.hotel_id = h.id
                WHERE h.subdomain = :subdomain
                ORDER BY r.room_number
            """), {"subdomain": hotel_subdomain}).fetchall()
        else:
            # Get all rooms (original behavior)
            rooms_result = db.execute(text("SELECT * FROM tablelink_rooms ORDER BY room_number")).fetchall()
        
        result = []
        for room in rooms_result:
            result.append({
                "room_number": room.room_number,
                "status": room.status,
                "code": room.code,
                "checkout_requested": getattr(room, 'checkout_requested', False),
                "has_extra_order": getattr(room, 'has_extra_order', False)
            })
        
        return JSONResponse(content=result)
    
    except Exception as e:
        print(f"Rooms error: {e}")
        # Return sample data if database fails
        sample_rooms = [
            {"room_number": 101, "status": "available", "code": "A1B", "checkout_requested": False, "has_extra_order": False},
            {"room_number": 102, "status": "available", "code": "C2D", "checkout_requested": False, "has_extra_order": False},
            {"room_number": 201, "status": "occupied", "code": "G4H", "checkout_requested": False, "has_extra_order": True}
        ]
        return JSONResponse(content=sample_rooms)

# Initialize sample data endpoint
@app.post("/init-sample-data")
async def init_sample_data(db: Session = Depends(get_db)):
    try:
        # Create sample hotel
        db.execute(text("""
            INSERT INTO tablelink_hotels (name, subdomain, plan_type, active, created_at)
            VALUES ('Luxury Grand Hotel', 'demo', 'trial', true, NOW())
            ON CONFLICT (subdomain) DO NOTHING
        """))
        
        # Get hotel ID
        hotel_result = db.execute(text("SELECT id FROM tablelink_hotels WHERE subdomain = 'demo'")).fetchone()
        hotel_id = hotel_result.id if hotel_result else 1
        
        # Create sample rooms
        rooms_data = [
            (101, "A1B"), (102, "C2D"), (103, "E3F"),
            (201, "G4H"), (202, "I5J"), (203, "K6L")
        ]
        
        for room_num, code in rooms_data:
            db.execute(text("""
                INSERT INTO tablelink_rooms (hotel_id, room_number, code, status)
                VALUES (:hotel_id, :room_num, :code, 'available')
                ON CONFLICT DO NOTHING
            """), {"hotel_id": hotel_id, "room_num": room_num, "code": code})
        
        # Create admin user (using restaurant_id column that exists)
        password_hash = get_password_hash("admin123")
        db.execute(text("""
            INSERT INTO tablelink_users (restaurant_id, username, password_hash, role, active)
            VALUES (:hotel_id, 'admin', :password_hash, 'admin', true)
            ON CONFLICT DO NOTHING
        """), {"hotel_id": hotel_id, "password_hash": password_hash})
        
        # Create sample menu items (using restaurant_id column that exists)
        menu_items = [
            ("Caesar Salad", "Fresh romaine, parmesan, croutons", 18.50, "Appetizers"),
            ("Grilled Salmon", "Atlantic salmon, lemon butter, vegetables", 32.00, "Main Course"),
            ("Beef Tenderloin", "Prime cut, red wine reduction, potatoes", 45.00, "Main Course"),
            ("Chocolate Cake", "Rich chocolate cake with vanilla ice cream", 12.00, "Desserts"),
            ("Club Sandwich", "Turkey, bacon, lettuce, tomato, fries", 22.00, "Light Meals"),
            ("Coffee", "Freshly brewed premium coffee", 6.00, "Beverages")
        ]
        
        for name, ingredients, price, category in menu_items:
            db.execute(text("""
                INSERT INTO tablelink_menu_items (restaurant_id, name, ingredients, price, category, active)
                VALUES (:hotel_id, :name, :ingredients, :price, :category, true)
                ON CONFLICT DO NOTHING
            """), {
                "hotel_id": hotel_id,
                "name": name,
                "ingredients": ingredients,
                "price": price,
                "category": category
            })
        
        db.commit()
        return {"message": "Sample data initialized successfully!"}
    
    except Exception as e:
        db.rollback()
        print(f"Init error: {e}")
        return {"message": f"Error initializing data: {str(e)}"}

@app.post("/business/update-hotel-info")
async def update_hotel_info(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        
        db.execute(text("""
            UPDATE tablelink_hotels SET 
                name = :name, 
                address = :address, 
                phone = :phone, 
                email = :email, 
                description = :description
            WHERE id = 1
        """), {
            "name": data.get('name'),
            "address": data.get('address'),
            "phone": data.get('phone'),
            "email": data.get('email'),
            "description": data.get('description')
        })
        
        db.commit()
        return {"message": "Hotel information updated successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error updating hotel information"}

@app.post("/business/update-header")
async def update_header_image(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        header_url = data.get('header_image_url')
        
        if hotel_subdomain:
            db.execute(text("""
                UPDATE tablelink_hotels SET header_image_url = :url WHERE subdomain = :subdomain
            """), {"url": header_url, "subdomain": hotel_subdomain})
        else:
            db.execute(text("""
                UPDATE tablelink_hotels SET header_image_url = :url WHERE id = 1
            """), {"url": header_url})
        
        db.commit()
        return {"message": "Header image updated successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error updating header image"}

@app.post("/business/update-logo")
async def update_logo(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        logo_url = data.get('logo_url')
        
        if hotel_subdomain:
            db.execute(text("""
                UPDATE tablelink_hotels SET logo_url = :url WHERE subdomain = :subdomain
            """), {"url": logo_url, "subdomain": hotel_subdomain})
        else:
            db.execute(text("""
                UPDATE tablelink_hotels SET logo_url = :url WHERE id = 1
            """), {"url": logo_url})
        
        db.commit()
        return {"message": "Logo updated successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error updating logo"}

@app.get("/business/room-details/{room_type}")
async def get_room_details(room_type: str, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        if hotel_subdomain:
            room_data = db.execute(text("""
                SELECT r.*, GROUP_CONCAT(rp.photo_url) as photos
                FROM tablelink_rooms r
                LEFT JOIN tablelink_room_photos rp ON r.room_type = rp.room_type AND r.hotel_id = rp.hotel_id
                JOIN tablelink_hotels h ON r.hotel_id = h.id
                WHERE r.room_type = :room_type AND h.subdomain = :subdomain
                GROUP BY r.room_type, r.price_per_night, r.max_guests, r.description
                LIMIT 1
            """), {"room_type": room_type, "subdomain": hotel_subdomain}).fetchone()
        else:
            room_data = db.execute(text("""
                SELECT r.*, GROUP_CONCAT(rp.photo_url) as photos
                FROM tablelink_rooms r
                LEFT JOIN tablelink_room_photos rp ON r.room_type = rp.room_type
                WHERE r.room_type = :room_type
                GROUP BY r.room_type, r.price_per_night, r.max_guests, r.description
                LIMIT 1
            """), {"room_type": room_type}).fetchone()
        
        if not room_data:
            return {"error": "Room type not found"}
        
        photos = room_data.photos.split(',') if room_data.photos else []
        if room_data.image_url:
            photos.insert(0, room_data.image_url)
        
        return {
            "room_type": room_data.room_type,
            "price_per_night": float(room_data.price_per_night or 0),
            "max_guests": room_data.max_guests or 2,
            "description": room_data.description,
            "total_rooms": 1,
            "photos": photos
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/business/add-room-photos")
async def add_room_photos(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        room_type = data.get('room_type')
        photos = data.get('photos', [])
        
        if hotel_subdomain:
            hotel = db.execute(text("SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain"), 
                              {"subdomain": hotel_subdomain}).fetchone()
            hotel_id = hotel.id if hotel else 1
        else:
            hotel_id = 1
        
        for photo_url in photos:
            db.execute(text("""
                INSERT INTO tablelink_room_photos (hotel_id, room_type, photo_url)
                VALUES (:hotel_id, :room_type, :photo_url)
            """), {"hotel_id": hotel_id, "room_type": room_type, "photo_url": photo_url})
        
        db.commit()
        return {"message": "Photos added successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error adding photos"}

@app.post("/business/update-room-type")
async def update_room_type(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        
        if hotel_subdomain:
            db.execute(text("""
                UPDATE tablelink_rooms SET 
                    room_type = :new_type, 
                    price_per_night = :price, 
                    max_guests = :guests, 
                    description = :description,
                    image_url = :image_url
                WHERE room_type = :original_type AND hotel_id = (
                    SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain
                )
            """), {
                "new_type": data['room_type'],
                "price": data['price_per_night'],
                "guests": data['max_guests'],
                "description": data['description'],
                "image_url": data.get('image_url', ''),
                "original_type": data['original_room_type'],
                "subdomain": hotel_subdomain
            })
        else:
            db.execute(text("""
                UPDATE tablelink_rooms SET 
                    room_type = :new_type, 
                    price_per_night = :price, 
                    max_guests = :guests, 
                    description = :description,
                    image_url = :image_url
                WHERE room_type = :original_type
            """), {
                "new_type": data['room_type'],
                "price": data['price_per_night'],
                "guests": data['max_guests'],
                "description": data['description'],
                "image_url": data.get('image_url', ''),
                "original_type": data['original_room_type']
            })
        
        db.commit()
        return {"message": "Room type updated successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error updating room type"}

@app.post("/business/update-room-image")
async def update_room_image(request: Request, hotel_subdomain: str = None, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        room_type = data.get('room_type')
        image_url = data.get('image_url')
        
        if hotel_subdomain:
            db.execute(text("""
                UPDATE tablelink_rooms SET image_url = :url 
                WHERE room_type = :room_type AND hotel_id = (
                    SELECT id FROM tablelink_hotels WHERE subdomain = :subdomain
                )
            """), {"url": image_url, "room_type": room_type, "subdomain": hotel_subdomain})
        else:
            db.execute(text("""
                UPDATE tablelink_rooms SET image_url = :url WHERE room_type = :room_type
            """), {"url": image_url, "room_type": room_type})
        
        db.commit()
        return {"message": "Room image updated successfully"}
    except Exception as e:
        db.rollback()
        return {"message": "Error updating room image"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)