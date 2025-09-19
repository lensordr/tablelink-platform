from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from models import Restaurant
from typing import Optional

class TenantContext:
    def __init__(self):
        self.restaurant_id: Optional[int] = None
        self.restaurant: Optional[Restaurant] = None

# Thread-local tenant context
import threading
tenant_context = threading.local()

def get_restaurant_from_subdomain(subdomain: str, db: Session) -> Optional[Restaurant]:
    """Get restaurant by subdomain"""
    return db.query(Restaurant).filter(
        Restaurant.subdomain == subdomain,
        Restaurant.active == True
    ).first()

def get_restaurant_from_request(request: Request, db: Session, original_path: str = None) -> Restaurant:
    """Extract restaurant from request (subdomain or path parameter)"""
    
    # Use original path if provided, otherwise use current path
    path = original_path or str(request.url.path)
    
    # Method 1: Extract from subdomain (for production)
    host = request.headers.get("host", "")
    if "." in host and not host.startswith("localhost"):
        subdomain = host.split(".")[0]
        restaurant = get_restaurant_from_subdomain(subdomain, db)
        if restaurant:
            return restaurant
    
    # Method 2: Extract from path parameter (for development)
    print(f"Tenant resolution: path={path}")
    if path.startswith("/r/"):
        parts = path.split("/")
        if len(parts) >= 3:
            subdomain = parts[2]
            print(f"Tenant resolution: extracted subdomain='{subdomain}'")
            restaurant = get_restaurant_from_subdomain(subdomain, db)
            if restaurant:
                print(f"Tenant resolution: found restaurant {restaurant.id} ({restaurant.name})")
                return restaurant
            else:
                print(f"Tenant resolution: no restaurant found for subdomain '{subdomain}'")
    
    # Method 2b: Check referer header for AJAX requests
    referer = request.headers.get('referer', '')
    print(f"Tenant resolution: checking referer={referer}")
    if '/r/' in referer:
        try:
            subdomain = referer.split('/r/')[1].split('/')[0]
            print(f"Tenant resolution: extracted subdomain from referer='{subdomain}'")
            restaurant = get_restaurant_from_subdomain(subdomain, db)
            if restaurant:
                print(f"Tenant resolution: found restaurant from referer {restaurant.id} ({restaurant.name})")
                return restaurant
        except Exception as e:
            print(f"Tenant resolution: error parsing referer: {e}")
    
    # Method 3: Default to demo restaurant for localhost only if no subdomain specified
    if ("localhost" in host or "127.0.0.1" in host) and not ('/r/' in path or '/r/' in referer):
        print(f"Tenant resolution: defaulting to demo restaurant")
        restaurant = db.query(Restaurant).filter(
            Restaurant.subdomain == 'demo',
            Restaurant.active == True
        ).first()
        if restaurant:
            return restaurant
    
    raise HTTPException(status_code=404, detail="Restaurant not found or inactive")

def set_tenant_context(restaurant: Restaurant):
    """Set the current tenant context"""
    if not hasattr(tenant_context, 'restaurant_id'):
        tenant_context.restaurant_id = None
        tenant_context.restaurant = None
    tenant_context.restaurant_id = restaurant.id
    tenant_context.restaurant = restaurant

def get_current_restaurant_id() -> int:
    """Get current restaurant ID from context"""
    if not hasattr(tenant_context, 'restaurant_id') or not tenant_context.restaurant_id:
        raise HTTPException(status_code=400, detail="No restaurant context")
    return tenant_context.restaurant_id

def get_current_restaurant() -> Restaurant:
    """Get current restaurant from context"""
    if not hasattr(tenant_context, 'restaurant') or not tenant_context.restaurant:
        raise HTTPException(status_code=400, detail="No restaurant context")
    return tenant_context.restaurant

def requires_plan(required_plan: str):
    """Decorator to check if restaurant has required plan"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            restaurant = get_current_restaurant()
            
            # Trial users get professional features
            if restaurant.plan_type == "trial":
                return func(*args, **kwargs)
            
            # Check plan hierarchy: professional > basic
            if required_plan == "professional" and restaurant.plan_type != "professional":
                raise HTTPException(status_code=403, detail="Professional plan required")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator