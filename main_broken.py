from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import create_tables, get_db, Hotel, Room, Staff, User, MenuItem, Order
from auth import verify_password

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
        "hotel_name": "Hotel Management System"
    })

# Client routes for room service
@app.get("/room/{room_number}", response_class=HTMLResponse)
async def room_page(request: Request, room_number: int):
    return templates.TemplateResponse("client.html", {
        "request": request, 
        "room_number": room_number,
        "hotel_name": "Hotel Management System"
    })

@app.get("/client/menu")
async def get_menu(request: Request, room: int, db: Session = Depends(get_db)):
    # Get room object
    room_obj = db.query(Room).filter(Room.room_number == room).first()
    if not room_obj:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get menu items
    menu_items = db.query(MenuItem).filter(MenuItem.active == True).all()
    
    # Group by category
    menu_by_category = {}
    for item in menu_items:
        category = item.category
        if category not in menu_by_category:
            menu_by_category[category] = []
        menu_by_category[category].append({
            "id": item.id,
            "name": item.name,
            "ingredients": item.ingredients,
            "price": item.price
        })
    
    return JSONResponse({
        "room_number": room,
        "room_code": room_obj.code,
        "hotel_name": "Hotel Management System",
        "menu": menu_by_category
    })

@app.get("/client/order_details/{room_number}")
async def get_client_order_details(request: Request, room_number: int, db: Session = Depends(get_db)):
    # Get existing order for room (simplified - no checkout functionality)
    return {"has_order": False}

@app.post("/client/order")
async def place_order(
    request: Request,
    room_number: int = Form(...),
    code: str = Form(...),
    items: str = Form(...),
    db: Session = Depends(get_db)
):
    # Verify room and code
    room = db.query(Room).filter(Room.room_number == room_number, Room.code == code).first()
    if not room:
        raise HTTPException(status_code=400, detail="Invalid room or code")
    
    import json
    try:
        order_items = json.loads(items)
    except:
        raise HTTPException(status_code=400, detail="Invalid items format")
    
    # Simple order placement - no checkout/tip functionality
    return {"message": "Room service order placed successfully"}

# Authentication routes
@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        # Find user in hotel database
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Simple token (for demo)
        return {"access_token": "demo_token", "token_type": "bearer", "role": user.role}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# Business dashboard
@app.get("/business/login", response_class=HTMLResponse)
async def business_login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "hotel_name": "Hotel Management System"
    })

@app.get("/business/dashboard", response_class=HTMLResponse)
async def business_dashboard(request: Request):
    return templates.TemplateResponse("business.html", {
        "request": request,
        "hotel_name": "Hotel Management System"
    })

@app.get("/business/rooms")
async def get_rooms_status(db: Session = Depends(get_db)):
    rooms = db.query(Room).all()
    result = [{
        "room_number": r.room_number, 
        "status": r.status, 
        "code": r.code, 
        "checkout_requested": r.checkout_requested, 
        "has_extra_order": r.has_extra_order
    } for r in rooms]
    return JSONResponse(content=result)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)