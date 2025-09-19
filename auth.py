from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models import User, get_db

# Configuration
SECRET_KEY = "restaurant-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(db: Session = Depends(get_db)):
    # Temporarily disabled authentication - return mock admin user
    from models import User
    mock_user = User()
    mock_user.id = 1
    mock_user.username = "admin"
    mock_user.role = "admin"
    mock_user.active = True
    return mock_user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def authenticate_user(db: Session, username: str, password: str, restaurant_id: int = None):
    from tenant import get_current_restaurant_id
    
    print(f"Auth: Looking for user '{username}' in restaurant {restaurant_id}")
    
    if restaurant_id is None:
        try:
            restaurant_id = get_current_restaurant_id()
        except:
            # Fallback to any user if no tenant context
            user = db.query(User).filter(User.username == username, User.active == True).first()
            if not user or not verify_password(password, user.password_hash):
                return False
            return user
    
    user = db.query(User).filter(
        User.username == username, 
        User.active == True,
        User.restaurant_id == restaurant_id
    ).first()
    
    if not user:
        print(f"Auth: No user found with username '{username}' in restaurant {restaurant_id}")
        # Debug: show all users in this restaurant
        all_users = db.query(User).filter(User.restaurant_id == restaurant_id).all()
        print(f"Auth: Available users in restaurant {restaurant_id}: {[(u.username, u.active) for u in all_users]}")
        return False
    
    if not verify_password(password, user.password_hash):
        print(f"Auth: Password verification failed for user '{username}'")
        return False
    
    print(f"Auth: Successfully authenticated user '{username}' in restaurant {restaurant_id}")
    return user