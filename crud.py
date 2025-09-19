from sqlalchemy.orm import Session
from models import Table, MenuItem, Order, OrderItem, Waiter, User, Restaurant
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract
from auth import get_password_hash
from tenant import get_current_restaurant_id

# Table operations
def get_all_tables(db: Session, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    return db.query(Table).filter(Table.restaurant_id == restaurant_id).all()

def get_table_by_number(db: Session, table_number: int, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    return db.query(Table).filter(
        Table.table_number == table_number,
        Table.restaurant_id == restaurant_id
    ).first()

def update_table_status(db: Session, table_number: int, status: str, restaurant_id: int = None):
    table = get_table_by_number(db, table_number, restaurant_id)
    if table:
        table.status = status
        db.commit()
        db.refresh(table)
    return table

# Menu operations
def get_active_menu_items(db: Session, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    return db.query(MenuItem).filter(
        MenuItem.active == True,
        MenuItem.restaurant_id == restaurant_id
    ).order_by(MenuItem.category, MenuItem.name).all()

def get_menu_items_by_category(db: Session, include_inactive: bool = False, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    
    query = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant_id)
    if not include_inactive:
        query = query.filter(MenuItem.active == True)
    
    items = query.order_by(MenuItem.category, MenuItem.name).all()
    categories = {}
    for item in items:
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)
    return categories

def get_menu_item_by_id(db: Session, item_id: int, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    return db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant_id
    ).first()

def toggle_menu_item_active(db: Session, item_id: int, restaurant_id: int = None):
    item = get_menu_item_by_id(db, item_id, restaurant_id)
    if item:
        item.active = not item.active
        db.commit()
        db.refresh(item)
    return item

def create_menu_item(db: Session, name: str, ingredients: str, price: float, category: str = 'Food', restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    item = MenuItem(
        restaurant_id=restaurant_id,
        name=name, 
        ingredients=ingredients, 
        price=price, 
        category=category
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

# Order operations
def create_order(db: Session, table_number: int, items: list, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    
    # Get table by number and restaurant
    table = get_table_by_number(db, table_number, restaurant_id)
    if not table:
        raise ValueError(f"Table {table_number} not found")
    
    order = Order(
        restaurant_id=restaurant_id,
        table_id=table.id
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    for item in items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item['product_id'],
            qty=item['qty'],
            customizations=item.get('customizations')
        )
        db.add(order_item)
    
    db.commit()
    return order

def add_items_to_order(db: Session, order_id: int, items: list):
    print(f"Adding items to order {order_id}: {items}")
    
    for item in items:
        # Always add as separate entry for extra orders to avoid mistakes
        print(f"Adding new extra item {item['product_id']} with qty {item['qty']}")
        order_item = OrderItem(
            order_id=order_id,
            product_id=item['product_id'],
            qty=item['qty'],
            is_extra_item=True,
            is_new_extra=True,
            customizations=item.get('customizations')
        )
        db.add(order_item)
        print(f"Added new item with is_new_extra=True")
    
    db.commit()
    print(f"Committed changes to order {order_id}")

def get_active_order_by_table(db: Session, table_number: int, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    
    # Get table first
    table = get_table_by_number(db, table_number, restaurant_id)
    if not table:
        return None
    
    return db.query(Order).filter(
        Order.table_id == table.id,
        Order.restaurant_id == restaurant_id,
        Order.status == 'active'
    ).first()

def finish_order(db: Session, table_number: int, restaurant_id: int = None):
    order = get_active_order_by_table(db, table_number, restaurant_id)
    if order:
        order.status = 'finished'
        db.commit()
        db.refresh(order)
    return order

def get_order_details(db: Session, table_number: int, restaurant_id: int = None):
    order = get_active_order_by_table(db, table_number, restaurant_id)
    if not order:
        return None
    
    details = {
        'order_id': order.id,
        'table_number': table_number,
        'created_at': order.created_at,
        'items': [],
        'total': 0
    }
    
    for order_item in order.order_items:
        item_total = order_item.menu_item.price * order_item.qty
        is_extra = getattr(order_item, 'is_extra_item', False)
        is_new_extra = getattr(order_item, 'is_new_extra', False)
        
        print(f"Item {order_item.menu_item.name}: is_extra_item={is_extra}, is_new_extra={is_new_extra}")
        
        details['items'].append({
            'name': order_item.menu_item.name,
            'price': order_item.menu_item.price,
            'qty': order_item.qty,
            'total': item_total,
            'is_extra_item': is_extra,
            'is_new_extra': is_new_extra,
            'customizations': order_item.customizations
        })
        details['total'] += item_total
    
    return details

# Initialize tables with sample data
def init_sample_data(db: Session, restaurant_id: int = None):
    # Skip if no restaurant context (during migration)
    try:
        if restaurant_id is None:
            restaurant_id = get_current_restaurant_id()
    except:
        # During migration, create for first restaurant
        restaurant = db.query(Restaurant).first()
        if not restaurant:
            return
        restaurant_id = restaurant.id
    
    # Create tables 1-10 with random 3-digit codes
    table_codes = ['123', '456', '789', '321', '654', '987', '147', '258', '369', '741']
    
    for i in range(1, 11):
        existing_table = db.query(Table).filter(
            Table.table_number == i,
            Table.restaurant_id == restaurant_id
        ).first()
        if not existing_table:
            table = Table(
                restaurant_id=restaurant_id,
                table_number=i, 
                code=table_codes[i-1]
            )
            db.add(table)
    
    # Create sample menu items
    sample_items = [
        {'name': 'Pizza Margherita', 'ingredients': 'Tomato, Mozzarella, Basil', 'price': 12.50, 'category': 'Food'},
        {'name': 'Pasta Carbonara', 'ingredients': 'Pasta, Eggs, Bacon, Parmesan', 'price': 14.00, 'category': 'Food'},
        {'name': 'Caesar Salad', 'ingredients': 'Lettuce, Croutons, Parmesan, Caesar Dressing', 'price': 9.50, 'category': 'Food'},
        {'name': 'Grilled Chicken', 'ingredients': 'Chicken Breast, Herbs, Vegetables', 'price': 16.00, 'category': 'Food'},
        {'name': 'Tiramisu', 'ingredients': 'Mascarpone, Coffee, Ladyfingers', 'price': 6.50, 'category': 'Desserts'}
    ]
    
    for item_data in sample_items:
        existing_item = db.query(MenuItem).filter(
            MenuItem.name == item_data['name'],
            MenuItem.restaurant_id == restaurant_id
        ).first()
        if not existing_item:
            item_data['restaurant_id'] = restaurant_id
            create_menu_item(db, **item_data)
    
    # Create default admin for this restaurant
    existing_admin = db.query(User).filter(
        User.username == 'admin',
        User.restaurant_id == restaurant_id
    ).first()
    if not existing_admin:
        create_user(db, 'admin', 'rrares', 'admin', restaurant_id)
    
    # Create sample waiters
    sample_waiters = ['John Smith', 'Maria Garcia', 'David Johnson']
    for waiter_name in sample_waiters:
        existing_waiter = db.query(Waiter).filter(
            Waiter.name == waiter_name,
            Waiter.restaurant_id == restaurant_id
        ).first()
        if not existing_waiter:
            create_waiter(db, waiter_name, restaurant_id)
    
    db.commit()

# Sales analytics functions
def get_sales_by_table_and_period(db: Session, period: str = 'day', target_date: date = None):
    if not target_date:
        target_date = date.today()
    
    query = db.query(
        Order.table_number,
        func.count(Order.id).label('total_orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_sales'),
        func.sum(Table.tip_amount).label('total_tips')
    ).join(OrderItem).join(MenuItem).join(Table, Order.table_number == Table.table_number)
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.filter(Order.status == 'finished')
    query = query.group_by(Order.table_number)
    
    return query.all()

def get_total_sales_summary(db: Session, period: str = 'day', target_date: date = None, waiter_id: int = None, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    
    if not target_date:
        target_date = date.today()
    
    # Get sales and orders
    sales_query = db.query(
        func.count(func.distinct(Order.id)).label('total_orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_sales')
    ).join(OrderItem).join(MenuItem).filter(Order.restaurant_id == restaurant_id)
    
    if period == 'day':
        sales_query = sales_query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        sales_query = sales_query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        sales_query = sales_query.filter(extract('year', Order.created_at) == target_date.year)
    
    sales_query = sales_query.filter(Order.status == 'finished')
    
    # Filter by waiter if specified
    if waiter_id:
        sales_query = sales_query.filter(Order.waiter_id == waiter_id)
    
    sales_result = sales_query.first()
    
    # Get tips from finished orders
    tips_query = db.query(
        func.sum(Order.tip_amount).label('total_tips')
    ).filter(
        Order.status == 'finished',
        Order.restaurant_id == restaurant_id
    )
    
    # Filter by waiter if specified
    if waiter_id:
        tips_query = tips_query.filter(Order.waiter_id == waiter_id)
    
    if period == 'day':
        tips_query = tips_query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        tips_query = tips_query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        tips_query = tips_query.filter(extract('year', Order.created_at) == target_date.year)
    
    tips_result = tips_query.first()
    
    return {
        'total_orders': sales_result.total_orders or 0,
        'total_sales': float(sales_result.total_sales or 0),
        'total_tips': float(tips_result.total_tips or 0) if tips_result.total_tips else 0.0
    }
# Waiter operations
def get_all_waiters(db: Session, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    return db.query(Waiter).filter(
        Waiter.active == True,
        Waiter.restaurant_id == restaurant_id
    ).all()

def create_waiter(db: Session, name: str, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    waiter = Waiter(restaurant_id=restaurant_id, name=name)
    db.add(waiter)
    db.commit()
    db.refresh(waiter)
    return waiter

def delete_waiter(db: Session, waiter_id: int, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    waiter = db.query(Waiter).filter(
        Waiter.id == waiter_id,
        Waiter.restaurant_id == restaurant_id
    ).first()
    if waiter:
        waiter.active = False
        db.commit()
    return waiter

def finish_order_with_waiter(db: Session, table_number: int, waiter_id: int, restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    
    order = get_active_order_by_table(db, table_number, restaurant_id)
    table = get_table_by_number(db, table_number, restaurant_id)
    if order and table:
        order.status = 'finished'
        order.waiter_id = waiter_id
        order.tip_amount = table.tip_amount or 0.0
        db.commit()
        db.refresh(order)
        
        # Update analytics records for real-time dashboard
        update_analytics_from_order(db, order, restaurant_id)
    return order

def update_analytics_from_order(db: Session, order, restaurant_id: int = None):
    """Create separate AnalyticsRecord entries for each category in the order"""
    from models import AnalyticsRecord
    
    if restaurant_id is None:
        restaurant_id = order.restaurant_id
    
    # Get table number from table relationship
    table_number = order.table.table_number if order.table else 0
    
    # Check if analytics records already exist for this order
    existing_records = db.query(AnalyticsRecord).filter(
        AnalyticsRecord.restaurant_id == restaurant_id,
        AnalyticsRecord.table_number == table_number,
        AnalyticsRecord.waiter_id == order.waiter_id,
        AnalyticsRecord.item_name.like(f"Order #{order.id}%")
    ).all()
    
    if existing_records:
        print(f"Analytics records already exist for order {order.id}, skipping")
        return
    
    # Group items by category
    category_totals = {}
    for item in order.order_items:
        category = item.menu_item.category
        if category not in category_totals:
            category_totals[category] = {'quantity': 0, 'total_price': 0}
        category_totals[category]['quantity'] += item.qty
        category_totals[category]['total_price'] += item.menu_item.price * item.qty
    
    # Create one record per category
    for category, totals in category_totals.items():
        analytics_record = AnalyticsRecord(
            restaurant_id=restaurant_id,
            table_number=table_number,
            waiter_id=order.waiter_id,
            item_name=f"Order #{order.id} - {category}",
            item_category=category,
            quantity=totals['quantity'],
            unit_price=totals['total_price'] / totals['quantity'],
            total_price=totals['total_price'],
            tip_amount=(order.tip_amount or 0) * (totals['total_price'] / sum(cat['total_price'] for cat in category_totals.values())),  # Proportional tip
            checkout_date=order.created_at
        )
        db.add(analytics_record)
    
    db.commit()
    print(f"Created {len(category_totals)} analytics records for order {order.id} categories: {list(category_totals.keys())}")

# User operations
def create_user(db: Session, username: str, password: str, role: str = 'waiter', restaurant_id: int = None):
    if restaurant_id is None:
        restaurant_id = get_current_restaurant_id()
    password_hash = get_password_hash(password)
    user = User(
        restaurant_id=restaurant_id,
        username=username, 
        password_hash=password_hash, 
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_username(db: Session, username: str, restaurant_id: int = None):
    if restaurant_id is None:
        try:
            restaurant_id = get_current_restaurant_id()
        except:
            # During migration or setup, find any user
            return db.query(User).filter(
                User.username == username, 
                User.active == True
            ).first()
    
    return db.query(User).filter(
        User.username == username, 
        User.active == True,
        User.restaurant_id == restaurant_id
    ).first()

def get_sales_by_waiter_and_period(db: Session, waiter_id: int, period: str = 'day', target_date: date = None):
    if not target_date:
        target_date = date.today()
    
    query = db.query(
        func.count(func.distinct(Order.id)).label('total_orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_sales'),
        func.sum(Order.tip_amount).label('total_tips')
    ).join(OrderItem).join(MenuItem).filter(Order.waiter_id == waiter_id)
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.filter(Order.status == 'finished')
    result = query.first()
    
    return {
        'waiter_id': waiter_id,
        'total_orders': result.total_orders or 0,
        'total_sales': float(result.total_sales or 0),
        'total_tips': float(result.total_tips or 0)
    }

def get_detailed_sales_data(db: Session, period: str = 'day', target_date: str = None, waiter_id: int = None):
    if not target_date:
        target_date = date.today()
    else:
        target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    
    # Get detailed order data
    query = db.query(
        Order.id.label('order_id'),
        Order.table_number,
        Order.created_at,
        Order.tip_amount.label('total_tips'),
        Waiter.name.label('waiter_name'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_sales')
    ).join(OrderItem).join(MenuItem).outerjoin(Waiter, Order.waiter_id == Waiter.id)
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'week':
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        query = query.filter(func.date(Order.created_at).between(start_of_week, end_of_week))
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.filter(Order.status == 'finished')
    
    if waiter_id:
        query = query.filter(Order.waiter_id == waiter_id)
    
    query = query.group_by(Order.id, Order.table_number, Order.created_at, Order.tip_amount, Waiter.name)
    query = query.order_by(Order.created_at.desc())
    
    orders = query.all()
    
    # Calculate summary - use same method as analytics
    # Count unique checkout dates from analytics records
    from models import AnalyticsRecord
    # Use same period logic as other functions
    if period == 'day':
        start_date = target_date
        end_date = target_date
    elif period == 'week':
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = target_date.replace(day=1)
        if target_date.month == 12:
            next_month = target_date.replace(year=target_date.year + 1, month=1)
        else:
            next_month = target_date.replace(month=target_date.month + 1)
        end_date = next_month - timedelta(days=1)
    elif period == 'year':
        start_date = target_date.replace(month=1, day=1)
        end_date = target_date.replace(month=12, day=31)
    else:
        start_date = target_date
        end_date = target_date
    
    # Simply use the actual count of filtered orders
    total_orders = len(orders)
    total_sales = sum(float(order.total_sales or 0) for order in orders)
    total_tips = sum(float(order.total_tips or 0) for order in orders)
    
    return {
        'summary': {
            'total_orders': total_orders,
            'total_sales': total_sales,
            'total_tips': total_tips
        },
        'table_sales': [
            {
                'order_id': order.order_id,
                'table_number': order.table_number,
                'waiter_name': order.waiter_name or 'Unknown',
                'total_sales': float(order.total_sales or 0),
                'total_tips': float(order.total_tips or 0),
                'created_at': order.created_at.isoformat()
            }
            for order in orders
        ]
    }

# Advanced Analytics Functions
def get_top_selling_items(db: Session, period: str = 'day', target_date: str = None, limit: int = 10):
    """Get top selling items by quantity and revenue"""
    if not target_date:
        target_date = date.today()
    else:
        target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    
    query = db.query(
        MenuItem.id,
        MenuItem.name,
        MenuItem.category,
        MenuItem.price,
        func.sum(OrderItem.qty).label('total_quantity'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_revenue'),
        func.count(func.distinct(Order.id)).label('order_frequency')
    ).join(OrderItem).join(Order).filter(Order.status == 'finished')
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'week':
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        query = query.filter(func.date(Order.created_at).between(start_of_week, end_of_week))
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.group_by(MenuItem.id, MenuItem.name, MenuItem.category, MenuItem.price)
    query = query.order_by(func.sum(OrderItem.qty).desc())
    query = query.limit(limit)
    
    return query.all()

def get_sales_trends(db: Session, days: int = 30):
    """Get daily sales trends for the last N days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    query = db.query(
        func.date(Order.created_at).label('date'),
        func.count(func.distinct(Order.id)).label('orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('revenue'),
        func.sum(Order.tip_amount).label('tips')
    ).join(OrderItem).join(MenuItem).filter(
        Order.status == 'finished',
        func.date(Order.created_at).between(start_date, end_date)
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at))
    
    return query.all()

def get_category_performance(db: Session, period: str = 'month', target_date: str = None):
    """Get performance by menu category"""
    if not target_date:
        target_date = date.today()
    else:
        target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    
    query = db.query(
        MenuItem.category,
        func.sum(OrderItem.qty).label('total_quantity'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_revenue'),
        func.count(func.distinct(MenuItem.id)).label('unique_items'),
        func.avg(MenuItem.price).label('avg_price')
    ).join(OrderItem).join(Order).filter(Order.status == 'finished')
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.group_by(MenuItem.category)
    query = query.order_by(func.sum(OrderItem.qty * MenuItem.price).desc())
    
    return query.all()

def get_hourly_sales_pattern(db: Session, target_date: str = None):
    """Get sales pattern by hour of day"""
    if not target_date:
        target_date = date.today()
    else:
        target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    
    query = db.query(
        extract('hour', Order.created_at).label('hour'),
        func.count(func.distinct(Order.id)).label('orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('revenue')
    ).join(OrderItem).join(MenuItem).filter(
        Order.status == 'finished',
        func.date(Order.created_at) == target_date
    ).group_by(extract('hour', Order.created_at)).order_by(extract('hour', Order.created_at))
    
    return query.all()

def get_waiter_performance(db: Session, period: str = 'month', target_date: str = None):
    """Get detailed waiter performance metrics"""
    if not target_date:
        target_date = date.today()
    else:
        target_date = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    
    query = db.query(
        Waiter.id,
        Waiter.name,
        func.count(func.distinct(Order.id)).label('total_orders'),
        func.sum(OrderItem.qty * MenuItem.price).label('total_sales'),
        func.sum(Order.tip_amount).label('total_tips'),
        func.avg(OrderItem.qty * MenuItem.price).label('avg_order_value'),
        func.count(func.distinct(Order.table_number)).label('tables_served')
    ).join(Order).join(OrderItem).join(MenuItem).filter(Order.status == 'finished')
    
    if period == 'day':
        query = query.filter(func.date(Order.created_at) == target_date)
    elif period == 'month':
        query = query.filter(
            extract('year', Order.created_at) == target_date.year,
            extract('month', Order.created_at) == target_date.month
        )
    elif period == 'year':
        query = query.filter(extract('year', Order.created_at) == target_date.year)
    
    query = query.group_by(Waiter.id, Waiter.name)
    query = query.order_by(func.sum(OrderItem.qty * MenuItem.price).desc())
    
    return query.all()