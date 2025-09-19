from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List
import sys
import os
from datetime import date, timedelta
from middleware import TenantMiddleware
from tenant import get_current_restaurant_id, get_current_restaurant, requires_plan
from models import Restaurant

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from models import create_tables, get_db, MenuItem, Order, OrderItem, Table, Waiter, User  # type: ignore
    from crud import (  # type: ignore
        init_sample_data, get_table_by_number, get_active_menu_items, get_menu_items_by_category,
        create_order, update_table_status, get_all_tables, get_order_details,
        finish_order, toggle_menu_item_active, create_menu_item, get_active_order_by_table, add_items_to_order,
        get_sales_by_table_and_period, get_total_sales_summary, get_all_waiters, create_waiter, delete_waiter, finish_order_with_waiter,
        get_sales_by_waiter_and_period, get_detailed_sales_data
    )
    from auth import authenticate_user, create_access_token, get_current_user, require_admin  # type: ignore
except ImportError as e:
    print(f"Import error: {e}")
    raise

# Initialize sample data
from contextlib import asynccontextmanager
try:
    from setup import is_setup_complete, apply_setup, get_setup_config  # type: ignore
except ImportError as e:
    print(f"Setup import error: {e}")
    raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    
    # Always initialize sample data
    db = next(get_db())
    init_sample_data(db)
    db.close()
    
    if is_setup_complete():
        config = get_setup_config()
        print(f"\nWelcome back to {config.get('restaurant_name', 'TablePulse')}!")
    else:
        print("\nSetup available at /setup - using default data for now")
    
    yield

app = FastAPI(lifespan=lifespan)

# Add tenant middleware
app.add_middleware(TenantMiddleware)

# Mount static files and templates
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Add routes to prevent HTTP warnings
@app.get("/favicon.ico")
async def favicon():
    return JSONResponse({"message": "No favicon"}, status_code=204)

@app.get("/robots.txt")
async def robots():
    return JSONResponse({"message": "No robots.txt"}, status_code=204)

@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    return JSONResponse({"message": "No apple touch icon"}, status_code=204)

def get_restaurant_name():
    try:
        restaurant = get_current_restaurant()
        return restaurant.name
    except:
        config = get_setup_config()
        return config.get('restaurant_name', 'TablePulse Restaurant')

# Setup routes
@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if is_setup_complete():
        return templates.TemplateResponse("setup_complete.html", {"request": request})
    return templates.TemplateResponse("setup.html", {"request": request})

# Admin/Onboarding routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/onboard", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})

@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page_alt(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})

@app.post("/onboard")
async def create_restaurant(
    restaurant_name: str = Form(...),
    admin_email: str = Form(...),
    admin_username: str = Form(...),
    admin_password: str = Form(...),
    table_count: int = Form(...),
    plan_type: str = Form("trial"),
    menu_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        from onboarding import create_new_restaurant
        
        if table_count < 1 or table_count > 100:
            return JSONResponse({
                "success": False,
                "error": "Table count must be between 1 and 100"
            }, status_code=400)
        
        menu_content = None
        if menu_file and menu_file.filename:
            menu_content = await menu_file.read()
        
        result = create_new_restaurant(
            db=db,
            restaurant_name=restaurant_name,
            admin_email=admin_email,
            admin_username=admin_username,
            admin_password=admin_password,
            table_count=table_count,
            plan_type=plan_type,
            menu_file_content=menu_content
        )
        
        if result['success']:
            return JSONResponse({
                "success": True,
                "message": "Restaurant created successfully!",
                "restaurant_name": restaurant_name,
                "subdomain": result['subdomain'],
                "login_url": result['login_url'],
                "admin_username": result['admin_username'],
                "admin_password": result['admin_password']
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result['error']
            }, status_code=400)
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.get("/admin/stats")
async def admin_stats(db: Session = Depends(get_db)):
    from models import AnalyticsRecord
    
    total_restaurants = db.query(func.count(Restaurant.id)).scalar() or 0
    active_restaurants = db.query(func.count(Restaurant.id)).filter(Restaurant.active == True).scalar() or 0
    total_revenue = db.query(func.sum(AnalyticsRecord.total_price)).scalar() or 0
    total_orders = db.query(func.count(AnalyticsRecord.id)).scalar() or 0
    
    return {
        "total_restaurants": total_restaurants,
        "active_restaurants": active_restaurants,
        "total_revenue": float(total_revenue),
        "total_orders": total_orders,
        "monthly_revenue": float(total_revenue) * 0.1
    }

@app.get("/admin/restaurants")
async def list_restaurants(db: Session = Depends(get_db)):
    from models import AnalyticsRecord, Table
    
    restaurants = db.query(Restaurant).all()
    restaurant_data = []
    
    for r in restaurants:
        total_orders = db.query(func.count(AnalyticsRecord.id)).filter(
            AnalyticsRecord.restaurant_id == r.id
        ).scalar() or 0
        
        total_revenue = db.query(func.sum(AnalyticsRecord.total_price)).filter(
            AnalyticsRecord.restaurant_id == r.id
        ).scalar() or 0
        
        table_count = db.query(func.count(Table.id)).filter(
            Table.restaurant_id == r.id
        ).scalar() or 0
        
        # Get admin credentials
        admin_user = db.query(User).filter(
            User.restaurant_id == r.id,
            User.role == 'admin'
        ).first()
        
        restaurant_data.append({
            "id": r.id,
            "name": r.name,
            "subdomain": r.subdomain,
            "plan_type": r.plan_type,
            "table_count": table_count,
            "active": r.active,
            "created_at": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
            "total_orders": total_orders,
            "total_revenue": float(total_revenue),
            "login_url": f"http://localhost:8000/r/{r.subdomain}/business/login",
            "admin_username": admin_user.username if admin_user else "N/A"
        })
    
    return {"restaurants": restaurant_data}

@app.post("/admin/restaurants/{restaurant_id}/toggle")
async def toggle_restaurant_status(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    restaurant.active = not restaurant.active
    db.commit()
    
    return {
        "success": True,
        "message": f"Restaurant {'enabled' if restaurant.active else 'disabled'}",
        "active": restaurant.active
    }

@app.post("/admin/restaurants/{restaurant_id}/plan")
async def update_restaurant_plan(
    restaurant_id: int,
    plan_type: str = Form(...),
    db: Session = Depends(get_db)
):
    if plan_type not in ['trial', 'basic', 'professional']:
        raise HTTPException(status_code=400, detail="Invalid plan type")
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    restaurant.plan_type = plan_type
    
    # Set trial end date for new trials
    if plan_type == "trial":
        from datetime import datetime, timedelta
        restaurant.trial_ends_at = datetime.utcnow() + timedelta(days=5)
    else:
        restaurant.trial_ends_at = None
    
    # Reactivate if upgrading from expired trial
    if plan_type in ['basic', 'professional']:
        restaurant.active = True
        restaurant.subscription_status = "active"
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Plan updated to {plan_type}",
        "plan_type": plan_type
    }

@app.post("/admin/restaurants/{restaurant_id}/reset-password")
async def reset_restaurant_password(
    restaurant_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    from auth import get_password_hash
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    admin_user = db.query(User).filter(
        User.restaurant_id == restaurant_id,
        User.role == 'admin'
    ).first()
    
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found")
    
    print(f"Resetting password for user {admin_user.username} in restaurant {restaurant_id}")
    admin_user.password_hash = get_password_hash(new_password)
    db.commit()
    db.refresh(admin_user)
    print(f"Password updated successfully. New hash: {admin_user.password_hash[:20]}...")
    
    return {
        "success": True,
        "message": "Password reset successfully",
        "new_password": new_password
    }

@app.delete("/admin/restaurants/{restaurant_id}")
async def delete_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    from models import AnalyticsRecord, OrderItem, Order, MenuItem, Waiter, Table, User
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        return JSONResponse({"success": False, "error": "Restaurant not found"}, status_code=404)
    
    if restaurant_id == 1 or restaurant.subdomain == 'demo':
        return JSONResponse({"success": False, "error": "Cannot delete demo restaurant"}, status_code=400)
    
    try:
        # Delete in correct order
        db.query(AnalyticsRecord).filter(AnalyticsRecord.restaurant_id == restaurant_id).delete()
        
        order_ids = db.query(Order.id).filter(Order.restaurant_id == restaurant_id).subquery()
        db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).delete(synchronize_session=False)
        
        db.query(Order).filter(Order.restaurant_id == restaurant_id).delete()
        db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant_id).delete()
        db.query(Waiter).filter(Waiter.restaurant_id == restaurant_id).delete()
        db.query(Table).filter(Table.restaurant_id == restaurant_id).delete()
        db.query(User).filter(User.restaurant_id == restaurant_id).delete()
        
        db.delete(restaurant)
        db.commit()
        
        return JSONResponse({"success": True, "message": f"Restaurant '{restaurant.name}' deleted successfully"})
        
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "error": f"Failed to delete: {str(e)}"}, status_code=500)

@app.post("/setup")
async def complete_setup(
    restaurant_name: str = Form(...),
    admin_username: str = Form(...),
    admin_password: str = Form(...),
    menu_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        print(f"Setup request received: {restaurant_name}, {admin_username}")
        
        if is_setup_complete():
            print("Setup already completed")
            return JSONResponse({"error": "Setup already completed"}, status_code=400)
        
        config = {
            'restaurant_name': restaurant_name,
            'admin_username': admin_username,
            'admin_password': admin_password
        }
        
        if menu_file and menu_file.filename:
            print(f"Menu file provided: {menu_file.filename}")
            menu_content = await menu_file.read()
            config['menu_file'] = menu_content
            config['menu_filename'] = menu_file.filename
        
        print("Applying setup...")
        apply_setup(config)
        print("Initializing sample data...")
        init_sample_data(db)
        print("Setup completed successfully")
        
        return JSONResponse({"message": "Setup completed successfully!", "redirect": "/business/login"})
    except Exception as e:
        print(f"Setup error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if not is_setup_complete():
        return templates.TemplateResponse("setup.html", {"request": request})
    return templates.TemplateResponse("welcome.html", {"request": request, "restaurant_name": get_restaurant_name()})

# Client routes
@app.get("/client", response_class=HTMLResponse)
async def client_page(request: Request, table: int = None):
    restaurant_name = get_restaurant_name()
    return templates.TemplateResponse("client.html", {
        "request": request, 
        "table_number": table,
        "restaurant_name": restaurant_name
    })

@app.get("/table/{table_number}", response_class=HTMLResponse)
async def table_page(request: Request, table_number: int):
    restaurant_name = get_restaurant_name()
    return templates.TemplateResponse("client.html", {
        "request": request, 
        "table_number": table_number,
        "restaurant_name": restaurant_name
    })

@app.get("/client/menu")
async def get_menu(request: Request, table: int, db: Session = Depends(get_db)):
    # Get restaurant_id from request state
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    
    # Force correct restaurant detection
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    print(f"Client menu API: Using restaurant_id={restaurant_id}, referer={referer}")
    
    table_obj = get_table_by_number(db, table, restaurant_id)
    if not table_obj:
        raise HTTPException(status_code=404, detail="Table not found")
    
    categories = get_menu_items_by_category(db, restaurant_id=restaurant_id)
    print(f"Client menu: Found {len(categories)} categories for restaurant {restaurant_id}")
    menu_by_category = {}
    for category, items in categories.items():
        menu_by_category[category] = [
            {
                "id": item.id,
                "name": item.name,
                "ingredients": item.ingredients,
                "price": item.price
            }
            for item in items
        ]
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    restaurant_name = restaurant.name if restaurant else "Restaurant"
    
    response = JSONResponse({
        "table_number": table,
        "table_code": table_obj.code,
        "restaurant_name": restaurant_name,
        "menu": menu_by_category
    })
    print(f"Client menu: Returning menu for {restaurant_name} with {sum(len(items) for items in menu_by_category.values())} items")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/client/order_details/{table_number}")
async def get_client_order_details(request: Request, table_number: int, db: Session = Depends(get_db)):
    # Get restaurant_id from request state
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    
    # Force correct restaurant detection
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    details = get_order_details(db, table_number, restaurant_id)
    table = get_table_by_number(db, table_number, restaurant_id)
    
    if not details:
        return {"has_order": False}
    
    return {
        "has_order": True, 
        "checkout_requested": table.checkout_requested if table else False,
        **details
    }

@app.post("/client/checkout")
async def request_checkout(
    request: Request,
    table_number: int = Form(...),
    checkout_method: str = Form(...),
    tip_amount: float = Form(...),
    db: Session = Depends(get_db)
):
    # Get restaurant_id from request state
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    table = get_table_by_number(db, table_number, restaurant_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    if table.status != 'occupied':
        raise HTTPException(status_code=400, detail="No active order for this table")
    
    table.checkout_requested = True
    table.checkout_method = checkout_method
    table.tip_amount = tip_amount
    db.commit()
    
    return {"message": f"Checkout requested with {checkout_method} and €{tip_amount:.2f} tip"}

@app.post("/client/order")
async def place_order(
    request: Request,
    table_number: int = Form(...),
    code: str = Form(...),
    items: str = Form(...),
    db: Session = Depends(get_db)
):
    # Get restaurant_id from request state
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    
    # Force correct restaurant detection
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    print(f"Client order API: Using restaurant_id={restaurant_id} for table {table_number}")
    
    table = get_table_by_number(db, table_number, restaurant_id)
    if not table or table.code != code:
        raise HTTPException(status_code=400, detail="Invalid table or code")
    
    import json
    try:
        order_items = json.loads(items)
    except:
        raise HTTPException(status_code=400, detail="Invalid items format")
    
    if table.checkout_requested:
        raise HTTPException(status_code=400, detail="Cannot place orders after checkout has been requested. Please wait for staff assistance.")
    
    existing_order = get_active_order_by_table(db, table_number, restaurant_id)
    
    if existing_order:
        add_items_to_order(db, existing_order.id, order_items)
        table.has_extra_order = True
        db.commit()
        return {"message": "Items added to existing order", "order_id": existing_order.id}
    else:
        order = create_order(db, table_number, order_items, restaurant_id)
        update_table_status(db, table_number, 'occupied', restaurant_id)
        return {"message": "Order placed successfully", "order_id": order.id}

# Authentication routes  
@app.post("/auth/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        # Direct extraction from referer URL
        referer = request.headers.get('referer', '')
        restaurant_id = None
        
        if '/r/' in referer:
            try:
                subdomain = referer.split('/r/')[1].split('/')[0]
                restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
                if restaurant:
                    restaurant_id = restaurant.id
                    print(f"Found restaurant from referer: {subdomain} -> {restaurant_id}")
            except Exception as e:
                print(f"Error parsing referer: {e}")
        
        if not restaurant_id:
            # Default to demo restaurant
            restaurant = db.query(Restaurant).filter(Restaurant.subdomain == 'demo').first()
            restaurant_id = restaurant.id if restaurant else 1
        
        print(f"Login attempt: username={username}, restaurant_id={restaurant_id}")
        
        user = authenticate_user(db, username, password, restaurant_id)
        if not user:
            print(f"Authentication failed for {username} in restaurant {restaurant_id}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={
            "sub": user.username, 
            "role": user.role,
            "restaurant_id": restaurant_id
        })
        return {"access_token": access_token, "token_type": "bearer", "role": user.role}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}

# Business routes
@app.get("/business/login", response_class=HTMLResponse)
async def business_login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "restaurant_name": get_restaurant_name()
    })



@app.get("/test-login", response_class=HTMLResponse)
async def test_login_page(request: Request):
    with open("test_login.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/business", response_class=HTMLResponse)
async def business_dashboard(request: Request):
    # Redirect to login
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/business/login")

@app.get("/business/dashboard", response_class=HTMLResponse)
async def business_dashboard_authenticated(request: Request, db: Session = Depends(get_db)):
    try:
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        
        # Check for expired trials and auto-deactivate
        if restaurant and restaurant.plan_type == "trial" and restaurant.trial_ends_at:
            from datetime import datetime
            if datetime.utcnow() > restaurant.trial_ends_at:
                restaurant.active = False
                restaurant.subscription_status = "expired"
                db.commit()
                return templates.TemplateResponse("trial_expired.html", {
                    "request": request,
                    "restaurant_name": restaurant.name
                })
        
        return templates.TemplateResponse("business.html", {
            "request": request, 
            "user": {"username": "admin", "role": "admin"},
            "restaurant_name": restaurant.name if restaurant else "Restaurant"
        })
    except Exception as e:
        print(f"Dashboard error: {e}")
        return templates.TemplateResponse("business.html", {
            "request": request, 
            "user": {"username": "admin", "role": "admin"},
            "restaurant_name": "Restaurant"
        })

@app.get("/business/qr-codes")
async def generate_qr_codes(request: Request, db: Session = Depends(get_db)):
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    
    # Fallback: detect from referer for AJAX requests
    referer = request.headers.get('referer', '')
    if '/r/' in referer and restaurant_id == 1:
        try:
            subdomain = referer.split('/r/')[1].split('/')[0]
            restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
            if restaurant:
                restaurant_id = restaurant.id
        except:
            pass
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    tables = db.query(Table).filter(Table.restaurant_id == restaurant_id).all()
    
    print(f"QR Codes API: restaurant_id={restaurant_id}, restaurant={restaurant.name if restaurant else 'None'}, tables_count={len(tables)}")
    
    qr_data = []
    for table in tables:
        # Generate the customer URL for each table
        if restaurant:
            table_url = f"https://tablelink.space/r/{restaurant.subdomain}/client?table={table.table_number}"
        else:
            table_url = f"https://tablelink.space/client?table={table.table_number}"
        
        qr_data.append({
            "table_number": table.table_number,
            "url": table_url,
            "code": table.code
        })
    
    print(f"QR Codes API: Generated {len(qr_data)} QR codes")
    return {"qr_codes": qr_data}

@app.get("/business/trial-status")
async def get_trial_status(request: Request, db: Session = Depends(get_db)):
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    
    # Fallback: detect from referer for AJAX requests
    referer = request.headers.get('referer', '')
    if '/r/' in referer and restaurant_id == 1:
        try:
            subdomain = referer.split('/r/')[1].split('/')[0]
            restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
            if restaurant:
                restaurant_id = restaurant.id
        except:
            pass
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    
    if not restaurant or restaurant.plan_type != "trial" or not restaurant.trial_ends_at:
        return {"show_warning": False}
    
    from datetime import datetime
    now = datetime.utcnow()
    days_left = (restaurant.trial_ends_at - now).days
    
    return {
        "show_warning": days_left <= 3 and days_left >= 0,
        "days_left": max(0, days_left),
        "expired": days_left < 0
    }

@app.get("/business/tables")
async def get_tables_status(request: Request, db: Session = Depends(get_db)):
    try:
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        
        # Fallback: detect from referer for AJAX requests
        referer = request.headers.get('referer', '')
        if '/r/' in referer and restaurant_id == 1:
            try:
                subdomain = referer.split('/r/')[1].split('/')[0]
                restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
                if restaurant:
                    restaurant_id = restaurant.id
                    print(f"Tables API: Detected restaurant_id={restaurant_id} from referer")
            except:
                pass
        
        print(f"Tables API: Using restaurant_id={restaurant_id}")
        tables = get_all_tables(db, restaurant_id)
        result = [{
            "table_number": t.table_number, 
            "status": t.status, 
            "code": t.code, 
            "checkout_requested": t.checkout_requested, 
            "has_extra_order": t.has_extra_order,
            "checkout_method": getattr(t, 'checkout_method', None),
            "tip_amount": getattr(t, 'tip_amount', 0.0)
        } for t in tables]
        print(f"Tables API: Returning {len(result)} tables")
        return JSONResponse(content=result)
    except Exception as e:
        print(f"Error getting tables: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content=[])

@app.get("/business/order/{table_number}")
async def get_business_order_details(request: Request, table_number: int, db: Session = Depends(get_db)):
    try:
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        return get_order_details(db, table_number, restaurant_id)
    except Exception as e:
        print(f"Error getting order details: {e}")
        return None

@app.post("/business/finish_order")
async def finish_table_order(
    request: Request,
    table_number: int = Form(...),
    waiter_id: int = Form(None),
    db: Session = Depends(get_db)
):
    try:
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        if waiter_id:
            finish_order_with_waiter(db, table_number, waiter_id, restaurant_id)
        else:
            finish_order(db, table_number, restaurant_id)
        return {"message": "Order finished successfully"}
    except Exception as e:
        print(f"Error finishing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/business/menu")
async def get_business_menu(db: Session = Depends(get_db)):
    try:
        restaurant_id = get_current_restaurant_id()
        categories = get_menu_items_by_category(db, include_inactive=True, restaurant_id=restaurant_id)
        menu_by_category = {}
        for category, items in categories.items():
            menu_by_category[category] = [
                {
                    "id": item.id,
                    "name": item.name,
                    "ingredients": item.ingredients,
                    "price": item.price,
                    "is_active": item.active
                }
                for item in items
            ]
        return menu_by_category
    except Exception as e:
        print(f"Error getting menu: {e}")
        return {}

@app.post("/business/menu/toggle")
async def toggle_menu_item(
    item_id: int = Form(...),
    db: Session = Depends(get_db)
):
    try:
        restaurant_id = get_current_restaurant_id()
        toggle_menu_item_active(db, item_id, restaurant_id)
        return {"message": "Menu item status updated"}
    except Exception as e:
        print(f"Error toggling menu item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/business/menu/add")
async def add_menu_item(
    name: str = Form(...),
    ingredients: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        restaurant_id = get_current_restaurant_id()
        create_menu_item(db, name, ingredients, price, category, restaurant_id)
        return {"message": "Menu item added successfully"}
    except Exception as e:
        print(f"Error adding menu item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def test_route():
    return {"message": "Server is working"}

@app.get("/debug/restaurants")
async def debug_restaurants(db: Session = Depends(get_db)):
    restaurants = db.query(Restaurant).all()
    return {
        "restaurants": [
            {
                "id": r.id,
                "name": r.name,
                "subdomain": r.subdomain,
                "active": r.active
            }
            for r in restaurants
        ]
    }

@app.get("/test-csv")
async def test_csv():
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Test', 'CSV', 'Download'])
    writer.writerow(['This', 'is', 'working'])
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=test.csv"}
    )

@app.post("/business/menu/upload")
async def upload_menu_file(
    request: Request,
    menu_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Get restaurant_id
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        
        print(f"Upload request for restaurant {restaurant_id}, file: {menu_file.filename}")
        
        if not menu_file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        file_content = await menu_file.read()
        print(f"File size: {len(file_content)} bytes")
        
        if menu_file.filename.endswith(('.xlsx', '.xls')):
            from setup import process_excel_content
            process_excel_content(db, file_content, restaurant_id)
        elif menu_file.filename.endswith('.pdf'):
            from setup import process_pdf_content
            process_pdf_content(db, file_content, restaurant_id)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use Excel (.xlsx, .xls) or PDF files.")
        
        return JSONResponse({"message": "Menu uploaded successfully"})
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"Upload failed: {str(e)}"}, status_code=500)



@app.get("/business/waiters")
async def get_waiters_list(request: Request, db: Session = Depends(get_db)):
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    
    # Fallback: detect from referer for AJAX requests
    referer = request.headers.get('referer', '')
    if '/r/' in referer and restaurant_id == 1:
        try:
            subdomain = referer.split('/r/')[1].split('/')[0]
            restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
            if restaurant:
                restaurant_id = restaurant.id
                print(f"Waiters API: Detected restaurant_id={restaurant_id} from referer")
        except:
            pass
    
    print(f"Waiters API: Using restaurant_id={restaurant_id}")
    waiters = get_all_waiters(db, restaurant_id)
    return {"waiters": waiters}

@app.post("/business/waiters/add")
async def add_waiter(
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    create_waiter(db, name)
    return {"message": "Waiter added successfully"}

@app.delete("/business/waiters/{waiter_id}")
async def remove_waiter(waiter_id: int, db: Session = Depends(get_db)):
    delete_waiter(db, waiter_id)
    return {"message": "Waiter removed successfully"}



@app.post("/business/mark_viewed/{table_number}")
async def mark_order_viewed(
    request: Request,
    table_number: int,
    db: Session = Depends(get_db)
):
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    table = get_table_by_number(db, table_number, restaurant_id)
    if table:
        table.has_extra_order = False
        
        # Clear is_new_extra flag from all order items for this table
        active_order = get_active_order_by_table(db, table_number, restaurant_id)
        if active_order:
            db.query(OrderItem).filter(
                OrderItem.order_id == active_order.id,
                OrderItem.is_new_extra == True
            ).update({OrderItem.is_new_extra: False})
        
        db.commit()
    return {"message": "Order marked as viewed"}

@app.get("/business/order_details/{table_number}")
async def get_order_details_route(request: Request, table_number: int, db: Session = Depends(get_db)):
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    return get_order_details(db, table_number, restaurant_id)

@app.post("/business/checkout_table/{table_number}")
async def checkout_table(
    request: Request,
    table_number: int,
    waiter_id: int = Form(...),
    db: Session = Depends(get_db)
):
    from models import AnalyticsRecord
    from datetime import datetime
    
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    finish_order_with_waiter(db, table_number, waiter_id, restaurant_id)
    table = get_table_by_number(db, table_number, restaurant_id)
    # Clear table status after checkout
    if table:
        table.status = 'free'
        table.checkout_requested = False
        table.has_extra_order = False
        table.checkout_method = None
        table.tip_amount = 0.0
        db.commit()
    return {"message": "Table checkout completed successfully"}

@app.get("/business/menu_items")
async def get_menu_items_route(request: Request, db: Session = Depends(get_db)):
    try:
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        print(f"Menu items API: Using restaurant_id={restaurant_id}")
        categories = get_menu_items_by_category(db, include_inactive=True, restaurant_id=restaurant_id)
        print(f"Found {len(categories)} categories for restaurant {restaurant_id}")
        items = []
        for category, category_items in categories.items():
            print(f"Processing category {category} with {len(category_items)} items")
            for item in category_items:
                items.append({
                    "id": item.id,
                    "name": item.name,
                    "ingredients": item.ingredients,
                    "price": item.price,
                    "active": item.active,
                    "category": category
                })
        print(f"Returning {len(items)} total items for restaurant {restaurant_id}")
        return {"items": items}
    except Exception as e:
        print(f"Error in menu_items_route: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/business/toggle_product/{item_id}")
async def toggle_product_route(item_id: int, db: Session = Depends(get_db)):
    toggle_menu_item_active(db, item_id)
    return {"message": "Product status updated"}

@app.post("/business/waiters")
async def add_waiter_route(
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    create_waiter(db, name)
    return {"message": "Waiter added successfully"}

@app.get("/business/top-menu-items")
async def get_top_menu_items(
    request: Request,
    period: str = "day",
    target_date: str = None,
    limit: int = 5,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    from analytics_service import get_analytics_for_period
    
    # Get restaurant_id
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    # Get the most recent date with data if no target_date provided
    if target_date is None:
        from models import AnalyticsRecord
        latest_date = db.query(func.max(func.date(AnalyticsRecord.checkout_date))).filter(
            AnalyticsRecord.restaurant_id == restaurant_id
        ).scalar()
        if latest_date:
            target_date = str(latest_date)
        else:
            from datetime import date
            target_date = date.today().isoformat()
    
    print(f"Top items API: period={period}, target_date={target_date}, limit={limit}, restaurant_id={restaurant_id}")
    
    # Use the same analytics service as the sales endpoint
    analytics_data = get_analytics_for_period(db, target_date, period, waiter_id, restaurant_id)
    
    # Extract top items from analytics data
    top_items = analytics_data.get('top_items', [])[:limit]
    
    result = {
        'items': [
            {
                'name': item['name'],
                'quantity': item['quantity_sold'],
                'revenue': float(item['revenue'])
            }
            for item in top_items
        ]
    }
    print(f"Returning: {result}")
    return result

@app.get("/business/sales")
async def get_sales_route(
    request: Request,
    period: str = "day",
    target_date: str = None,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    from models import AnalyticsRecord
    
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    
    # Fallback: detect from referer for AJAX requests
    referer = request.headers.get('referer', '')
    if '/r/' in referer and restaurant_id == 1:
        try:
            subdomain = referer.split('/r/')[1].split('/')[0]
            restaurant = db.query(Restaurant).filter(Restaurant.subdomain == subdomain).first()
            if restaurant:
                restaurant_id = restaurant.id
                print(f"Sales API: Detected restaurant_id={restaurant_id} from referer")
        except:
            pass
    
    print(f"Sales API: Using restaurant_id={restaurant_id} from middleware")
    
    # Get the most recent date with data if no target_date provided
    if target_date is None:
        latest_date = db.query(func.max(func.date(AnalyticsRecord.checkout_date))).filter(
            AnalyticsRecord.restaurant_id == restaurant_id
        ).scalar()
        if latest_date:
            target_date = str(latest_date)
        else:
            from datetime import date
            target_date = date.today().isoformat()
    
    from analytics_service import get_analytics_for_period
    print(f"Sales API: period={period}, target_date={target_date}, waiter_id={waiter_id}, restaurant_id={restaurant_id}")
    result = get_analytics_for_period(db, target_date, period, waiter_id, restaurant_id)
    print(f"Sales API result for restaurant {restaurant_id}: {result['summary']}")
    return {
        'summary': result['summary'],
        'table_sales': []
    }

@app.get("/business/sales/download/csv")
async def download_sales_csv(
    period: str = "day",
    target_date: str = None,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    if target_date is None:
        from datetime import date
        target_date = date.today().isoformat()
    
    try:
        data = get_detailed_sales_data(db, period, target_date, waiter_id)
    except Exception as e:
        print(f"Error getting sales data: {e}")
        data = {'summary': {'total_orders': 0, 'total_sales': 0, 'total_tips': 0}, 'table_sales': []}
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Order ID', 'Table Number', 'Waiter', 'Sales', 'Tips', 'Date'])
    
    # Write data
    if data.get('table_sales'):
        for order in data['table_sales']:
            writer.writerow([
                order['order_id'],
                order['table_number'],
                order['waiter_name'],
                f"€{order['total_sales']:.2f}",
                f"€{order['total_tips']:.2f}",
                order['created_at']
            ])
    else:
        writer.writerow(['No sales data available for this period', '', '', '', '', ''])
    
    # Write summary
    writer.writerow([])
    writer.writerow(['SUMMARY'])
    writer.writerow(['Total Orders', data['summary']['total_orders']])
    writer.writerow(['Total Sales', f"€{data['summary']['total_sales']:.2f}"])
    writer.writerow(['Total Tips', f"€{data['summary']['total_tips']:.2f}"])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sales_{period}_{target_date}.csv"}
    )

@app.get("/business/sales/download/excel")
async def download_sales_excel(
    period: str = "day",
    target_date: str = None,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="Excel export not available")
    import io
    from fastapi.responses import StreamingResponse
    
    if target_date is None:
        from datetime import date
        target_date = date.today().isoformat()
    
    data = get_detailed_sales_data(db, period, target_date, waiter_id)
    
    # Create DataFrame
    df = pd.DataFrame(data['table_sales'])
    if not df.empty:
        df = df[['order_id', 'table_number', 'waiter_name', 'total_sales', 'total_tips', 'created_at']]
        df.columns = ['Order ID', 'Table Number', 'Waiter', 'Sales (€)', 'Tips (€)', 'Date']
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sales Data', index=False)
        
        # Add summary sheet
        summary_df = pd.DataFrame([
            ['Total Orders', data['summary']['total_orders']],
            ['Total Sales (€)', data['summary']['total_sales']],
            ['Total Tips (€)', data['summary']['total_tips']]
        ], columns=['Metric', 'Value'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=sales_{period}_{target_date}.xlsx"}
    )

@app.get("/business/analytics/dashboard")
async def get_analytics_dashboard(
    request: Request,
    target_date: str = None,
    period: str = "day",
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    try:
        # Get restaurant_id from request
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        
        # Check plan access
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if restaurant and restaurant.plan_type not in ["professional", "trial"]:
            raise HTTPException(status_code=403, detail="Professional plan required for advanced analytics")
        
        from analytics_service import get_analytics_for_period
        
        if target_date is None:
            from datetime import date
            target_date = date.today().isoformat()
        
        print(f"Analytics dashboard: Using restaurant_id={restaurant_id}")
        result = get_analytics_for_period(db, target_date, period, waiter_id, restaurant_id)
        
        # Limit response size to prevent Content-Length issues
        limited_result = {
            "summary": result.get('summary', {"total_orders": 0, "total_sales": 0, "total_tips": 0}),
            "top_items": result.get('top_items', [])[:10],  # Limit to 10 items
            "categories": result.get('categories', [])[:5],   # Limit to 5 categories
            "trends": result.get('trends', [])[-7:],          # Last 7 days only
            "waiters": result.get('waiters', [])[:10]         # Limit to 10 waiters
        }
        
        return JSONResponse(content=limited_result)
        
    except HTTPException:
        raise
    except Exception as e:
        error_response = {
            "summary": {"total_orders": 0, "total_sales": 0, "total_tips": 0},
            "top_items": [],
            "categories": [],
            "trends": [],
            "waiters": [],
            "error": str(e)[:100]  # Limit error message length
        }
        return JSONResponse(content=error_response)

@app.get("/business/analytics/top-items")
async def get_top_items(
    request: Request,
    period: str = "day",
    target_date: str = None,
    limit: int = 10,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    try:
        # Get restaurant_id
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        
        from analytics_service import get_top_items_by_period
        # Ensure limit doesn't exceed 50 to prevent large responses
        safe_limit = min(limit, 50)
        result = get_top_items_by_period(db, period, target_date, safe_limit, waiter_id, restaurant_id)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)[:100], "top_items": []})

@app.get("/business/analytics/item-trends/{item_name}")
async def get_item_trends(
    request: Request,
    item_name: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    # Get restaurant_id
    restaurant_id = getattr(request.state, 'restaurant_id', 1)
    referer = request.headers.get('referer', '')
    if '/r/marios' in referer:
        restaurant_id = 2
    elif '/r/sushi' in referer:
        restaurant_id = 3
    
    from analytics_service import get_item_performance_trends
    return get_item_performance_trends(db, item_name, days, restaurant_id)

@app.get("/business/analytics/categories")
async def get_category_analytics(
    request: Request,
    period: str = "month",
    target_date: str = None,
    waiter_id: int = None,
    db: Session = Depends(get_db)
):
    try:
        # Get restaurant_id
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer:
            restaurant_id = 2
        elif '/r/sushi' in referer:
            restaurant_id = 3
        
        from analytics_service import get_category_comparison
        result = get_category_comparison(db, period, target_date, waiter_id, restaurant_id)
        # Limit categories to prevent large responses
        if 'categories' in result:
            result['categories'] = result['categories'][:20]
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)[:100], "categories": []})

@app.get("/business/analytics")
async def analytics_page(request: Request, db: Session = Depends(get_db)):
    try:
        # Get restaurant_id from request
        restaurant_id = getattr(request.state, 'restaurant_id', 1)
        referer = request.headers.get('referer', '')
        if '/r/marios' in referer or '/r/marios' in str(request.url):
            restaurant_id = 2
        elif '/r/sushi' in referer or '/r/sushi' in str(request.url):
            restaurant_id = 3
        
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        print(f"Analytics page: restaurant_id={restaurant_id}, plan={restaurant.plan_type if restaurant else 'unknown'}")
        
        # Check if restaurant has professional plan or is in trial
        if not restaurant or restaurant.plan_type not in ["professional", "trial"]:
            # Show upgrade page for basic plan
            return templates.TemplateResponse("upgrade_required.html", {
                "request": request,
                "restaurant_name": restaurant.name if restaurant else "Restaurant",
                "current_plan": restaurant.plan_type if restaurant else "basic"
            })
        
        return templates.TemplateResponse("simple_analytics.html", {"request": request})
    except Exception as e:
        print(f"Analytics page error: {e}")
        return templates.TemplateResponse("simple_analytics.html", {"request": request})

@app.get("/business/analytics/export/csv")
async def export_analytics_csv(
    period: str = "month",
    target_date: str = None,
    db: Session = Depends(get_db)
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from analytics_service import get_top_items_by_period
    
    if target_date is None:
        from datetime import date
        target_date = date.today().isoformat()
    
    data = get_top_items_by_period(db, period, target_date, 50)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Rank', 'Item Name', 'Category', 'Quantity Sold', 'Revenue', 'Orders', 'Avg Price', 'Avg Revenue/Order'])
    
    # Write data
    for i, item in enumerate(data['top_items'], 1):
        writer.writerow([
            i,
            item['name'],
            item['category'],
            item['quantity_sold'],
            f"€{item['revenue']:.2f}",
            item['orders_appeared_in'],
            f"€{item['avg_price']:.2f}",
            f"€{item['avg_revenue_per_order']:.2f}"
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=top_items_{period}_{target_date}.csv"}
    )

@app.get("/debug/database")
async def debug_database(period: str = "day", db: Session = Depends(get_db)):
    from models import AnalyticsRecord, Waiter
    from datetime import date
    
    today = date.today()
    
    # Calculate date range based on period
    if period == "day":
        start_date = today
        end_date = today
    elif period == "month":
        start_date = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1)
        else:
            next_month = today.replace(month=today.month + 1)
        end_date = next_month - timedelta(days=1)
    else:
        start_date = today
        end_date = today
    
    # Get analytics records for the period
    records = db.query(AnalyticsRecord).filter(
        func.date(AnalyticsRecord.checkout_date) >= start_date,
        func.date(AnalyticsRecord.checkout_date) <= end_date
    ).all()
    
    # Get waiter names
    waiters = {w.id: w.name for w in db.query(Waiter).all()}
    
    # Group by waiter
    waiter_stats = {}
    total_sales = 0
    total_tips = 0
    total_orders = len(records)
    
    for record in records:
        waiter_name = waiters.get(record.waiter_id, f'Waiter {record.waiter_id}')
        if waiter_name not in waiter_stats:
            waiter_stats[waiter_name] = {'orders': 0, 'sales': 0, 'tips': 0}
        
        waiter_stats[waiter_name]['orders'] += 1
        waiter_stats[waiter_name]['sales'] += record.total_price
        waiter_stats[waiter_name]['tips'] += record.tip_amount
        
        total_sales += record.total_price
        total_tips += record.tip_amount
    
    return {
        'date': today.isoformat(),
        'total_records': total_orders,
        'total_sales': total_sales,
        'total_tips': total_tips,
        'waiter_breakdown': waiter_stats,
        'raw_records': [
            {
                'waiter': waiters.get(r.waiter_id, f'Waiter {r.waiter_id}'),
                'table': r.table_number,
                'sales': r.total_price,
                'tips': r.tip_amount,
                'date': r.checkout_date.isoformat()
            } for r in records[:10]  # Show first 10 records
        ]
    }

@app.get("/export/sales-csv")
async def export_sales_csv_simple(
    period: str = "day",
    target_date: str = None,
    db: Session = Depends(get_db)
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from models import AnalyticsRecord
    from datetime import datetime
    
    if target_date is None:
        from datetime import date
        target_date = date.today().isoformat()
    
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    
    try:
        print(f"CSV Export: period={period}, target_date={target_date}")
        # Get order data
        data = get_detailed_sales_data(db, period, target_date, None)
        print(f"CSV Export: Found {len(data.get('table_sales', []))} orders")
        
        # Get analytics order count using same period logic as dashboard
        from datetime import timedelta
        
        if period == "day":
            start_date = target_date_obj
            end_date = target_date_obj
        elif period == "week":
            start_date = target_date_obj - timedelta(days=target_date_obj.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = target_date_obj.replace(day=1)
            next_month = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
            end_date = next_month - timedelta(days=1)
        else:  # year
            start_date = target_date_obj.replace(month=1, day=1)
            end_date = target_date_obj.replace(month=12, day=31)
        
        analytics_orders = db.query(
            func.count(func.distinct(AnalyticsRecord.checkout_date))
        ).filter(
            func.date(AnalyticsRecord.checkout_date) >= start_date,
            func.date(AnalyticsRecord.checkout_date) <= end_date
        ).scalar() or 0
        
        # Override order count with analytics count
        data['summary']['total_orders'] = analytics_orders
        
        # If analytics shows fewer orders, limit the CSV data to match
        if analytics_orders < len(data.get('table_sales', [])):
            # Keep only the most recent orders to match analytics count
            data['table_sales'] = data['table_sales'][:analytics_orders]
        
    except Exception as e:
        data = {'summary': {'total_orders': 0, 'total_sales': 0, 'total_tips': 0}, 'table_sales': []}
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Order ID', 'Table Number', 'Waiter', 'Sales', 'Tips', 'Date'])
    
    if data.get('table_sales'):
        for order in data['table_sales']:
            writer.writerow([
                order['order_id'],
                order['table_number'],
                order['waiter_name'],
                f"€{order['total_sales']:.2f}",
                f"€{order['total_tips']:.2f}",
                order['created_at']
            ])
    else:
        writer.writerow(['No sales data available', '', '', '', '', ''])
    
    writer.writerow([])
    writer.writerow(['SUMMARY'])
    writer.writerow(['Total Orders', data['summary']['total_orders']])
    writer.writerow(['Total Sales', f"€{data['summary']['total_sales']:.2f}"])
    writer.writerow(['Total Tips', f"€{data['summary']['total_tips']:.2f}"])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sales_{period}_{target_date}.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)