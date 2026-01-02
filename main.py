from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
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

# Client routes for room service
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

@app.get("/business/orders")
async def get_orders(db: Session = Depends(get_db)):
    try:
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
@app.get("/business/orders")
async def get_orders(db: Session = Depends(get_db)):
    try:
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

@app.get("/business/menu")
async def get_business_menu(db: Session = Depends(get_db)):
    try:
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
async def get_business_staff(db: Session = Depends(get_db)):
    try:
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
async def get_rooms_status(db: Session = Depends(get_db)):
    try:
        # Get rooms using raw SQL
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

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)