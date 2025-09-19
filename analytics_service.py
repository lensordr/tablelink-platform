from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, desc
from datetime import datetime, date, timedelta
from models import AnalyticsRecord, Waiter, MenuItem
from typing import Optional, Dict, List

def get_analytics_for_period(db: Session, target_date: str, period: str = "day", waiter_id: int = None, restaurant_id: int = None):
    """Get analytics data for a specific period"""
    try:
        target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        
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
        else:  # year - from Jan 1 to current date (or selected date)
            start_date = target_date_obj.replace(month=1, day=1)
            end_date = target_date_obj  # Up to the selected date, not end of year
        
        # Count total analytics records as orders (each record = 1 order)
        orders_query = db.query(
            func.count(AnalyticsRecord.id)
        ).filter(
            func.date(AnalyticsRecord.checkout_date) >= start_date,
            func.date(AnalyticsRecord.checkout_date) <= end_date
        )
        if restaurant_id:
            orders_query = orders_query.filter(AnalyticsRecord.restaurant_id == restaurant_id)
        if waiter_id:
            orders_query = orders_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        total_orders = orders_query.scalar() or 0
        
        # Get totals
        totals_query = db.query(
            func.sum(AnalyticsRecord.total_price).label('total_sales'),
            func.sum(AnalyticsRecord.tip_amount).label('total_tips')
        ).filter(
            func.date(AnalyticsRecord.checkout_date) >= start_date,
            func.date(AnalyticsRecord.checkout_date) <= end_date
        )
        if restaurant_id:
            totals_query = totals_query.filter(AnalyticsRecord.restaurant_id == restaurant_id)
        if waiter_id:
            totals_query = totals_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        totals = totals_query.first()
        
        # Top items from actual orders
        from models import Order, OrderItem, MenuItem
        top_items_query = db.query(
            MenuItem.name.label('name'),
            func.sum(OrderItem.qty).label('quantity'),
            func.sum(OrderItem.qty * MenuItem.price).label('revenue')
        ).join(OrderItem).join(Order).filter(
            Order.status == 'finished',
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date
        )
        if restaurant_id:
            top_items_query = top_items_query.filter(Order.restaurant_id == restaurant_id)
        if waiter_id:
            top_items_query = top_items_query.filter(Order.waiter_id == waiter_id)
        top_items = top_items_query.group_by(MenuItem.id, MenuItem.name).order_by(
            func.sum(OrderItem.qty).desc()
        ).limit(10).all()
        
        # Categories
        categories_query = db.query(
            AnalyticsRecord.item_category.label('category'),
            func.sum(AnalyticsRecord.quantity).label('quantity_sold'),
            func.sum(AnalyticsRecord.total_price).label('revenue')
        ).filter(
            func.date(AnalyticsRecord.checkout_date) >= start_date,
            func.date(AnalyticsRecord.checkout_date) <= end_date
        )
        if restaurant_id:
            categories_query = categories_query.filter(AnalyticsRecord.restaurant_id == restaurant_id)
        if waiter_id:
            categories_query = categories_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        categories = categories_query.group_by(AnalyticsRecord.item_category).all()
        
        # Waiter performance - count distinct orders
        waiter_performance_query = db.query(
            AnalyticsRecord.waiter_id,
            func.count(func.distinct(func.substr(AnalyticsRecord.item_name, 1, func.instr(AnalyticsRecord.item_name, ' - ') - 1))).label('total_orders'),
            func.sum(AnalyticsRecord.total_price).label('total_sales'),
            func.sum(AnalyticsRecord.tip_amount).label('total_tips'),
            func.sum(AnalyticsRecord.quantity).label('total_items')
        ).filter(
            func.date(AnalyticsRecord.checkout_date) >= start_date,
            func.date(AnalyticsRecord.checkout_date) <= end_date
        )
        if restaurant_id:
            waiter_performance_query = waiter_performance_query.filter(AnalyticsRecord.restaurant_id == restaurant_id)
        if waiter_id:
            waiter_performance_query = waiter_performance_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        waiter_performance = waiter_performance_query.group_by(AnalyticsRecord.waiter_id).all()
        
        # Get waiter names (only from current restaurant)
        waiters_data = []
        for wp in waiter_performance:
            waiter_query = db.query(Waiter).filter(Waiter.id == wp.waiter_id)
            if restaurant_id:
                waiter_query = waiter_query.filter(Waiter.restaurant_id == restaurant_id)
            waiter = waiter_query.first()
            
            if waiter:  # Only include waiters from current restaurant
                waiters_data.append({
                    'name': waiter.name,
                    'total_orders': wp.total_orders,
                    'total_sales': float(wp.total_sales or 0),
                    'total_tips': float(wp.total_tips or 0),
                    'total_items': wp.total_items or 0,
                    'avg_order_value': float(wp.total_sales or 0) / max(wp.total_orders, 1)
                })
        
        # Trends (last 7 days)
        trends = []
        for i in range(7):
            trend_date = target_date_obj - timedelta(days=6-i)
            day_data_query = db.query(
                func.count(func.distinct(func.substr(AnalyticsRecord.item_name, 1, func.instr(AnalyticsRecord.item_name, ' - ') - 1))).label('orders'),
                func.sum(AnalyticsRecord.total_price).label('revenue')
            ).filter(
                func.date(AnalyticsRecord.checkout_date) == trend_date
            )
            if restaurant_id:
                day_data_query = day_data_query.filter(AnalyticsRecord.restaurant_id == restaurant_id)
            if waiter_id:
                day_data_query = day_data_query.filter(AnalyticsRecord.waiter_id == waiter_id)
            day_data = day_data_query.first()
            
            trends.append({
                'date': trend_date.isoformat(),
                'orders': day_data.orders or 0,
                'revenue': float(day_data.revenue or 0)
            })
        
        # Recalculate summary based on filtered waiters data
        filtered_total_orders = sum(w['total_orders'] for w in waiters_data)
        filtered_total_sales = sum(w['total_sales'] for w in waiters_data)
        filtered_total_tips = sum(w['total_tips'] for w in waiters_data)
        
        return {
            'summary': {
                'total_orders': filtered_total_orders,
                'total_sales': filtered_total_sales,
                'total_tips': filtered_total_tips
            },
            'top_items': [
                {
                    'name': item.name,
                    'quantity_sold': item.quantity,
                    'revenue': float(item.revenue),
                    'category': 'Food'  # Default category since we don't have it in this query
                }
                for item in top_items
            ],
            'categories': [
                {
                    'category': cat.category,
                    'quantity_sold': cat.quantity_sold,
                    'revenue': float(cat.revenue)
                }
                for cat in categories
            ],
            'trends': trends,
            'waiters': waiters_data
        }
        
    except Exception as e:
        print(f"Analytics error: {e}")
        return {
            'summary': {'total_orders': 0, 'total_sales': 0, 'total_tips': 0},
            'top_items': [],
            'categories': [],
            'trends': [],
            'waiters': [],
            'error': str(e)
        }

def get_top_items_by_period(db: Session, period: str = "day", target_date: str = None, limit: int = 10, waiter_id: int = None, restaurant_id: int = None) -> Dict:
    """Get top selling items for day/week/month with detailed analytics"""
    try:
        if target_date is None:
            target_date_obj = date.today()
        else:
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # Calculate date range
        if period == "day":
            start_date = target_date_obj
            end_date = target_date_obj
        elif period == "week":
            start_date = target_date_obj - timedelta(days=target_date_obj.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = target_date_obj.replace(day=1)
            if target_date_obj.month == 12:
                next_month = target_date_obj.replace(year=target_date_obj.year + 1, month=1)
            else:
                next_month = target_date_obj.replace(month=target_date_obj.month + 1)
            end_date = next_month - timedelta(days=1)
        elif period == "year":
            start_date = target_date_obj.replace(month=1, day=1)
            end_date = target_date_obj
        
        # Query top items from actual orders
        from models import Order, OrderItem, MenuItem
        top_items_query = db.query(
            MenuItem.name,
            MenuItem.category,
            func.sum(OrderItem.qty).label('total_quantity'),
            func.sum(OrderItem.qty * MenuItem.price).label('total_revenue'),
            func.count(func.distinct(Order.id)).label('orders_count'),
            func.avg(MenuItem.price).label('avg_price')
        ).join(OrderItem).join(Order).filter(
            and_(
                Order.status == 'finished',
                func.date(Order.created_at) >= start_date,
                func.date(Order.created_at) <= end_date
            )
        )
        if waiter_id:
            top_items_query = top_items_query.filter(Order.waiter_id == waiter_id)
        top_items = top_items_query.group_by(
            MenuItem.id,
            MenuItem.name,
            MenuItem.category
        ).order_by(
            desc(func.sum(OrderItem.qty))
        ).limit(limit).all()
        
        # Format results
        items_data = []
        for item in top_items:
            items_data.append({
                'name': item.name,
                'category': item.category,
                'quantity_sold': item.total_quantity,
                'revenue': float(item.total_revenue),
                'orders_appeared_in': item.orders_count,
                'avg_price': float(item.avg_price),
                'avg_revenue_per_order': float(item.total_revenue) / max(item.orders_count, 1)
            })
        
        # Get period summary
        period_summary_query = db.query(
            func.count(func.distinct(AnalyticsRecord.checkout_date)).label('total_orders'),
            func.sum(AnalyticsRecord.total_price).label('total_revenue'),
            func.count(func.distinct(AnalyticsRecord.item_name)).label('unique_items')
        ).filter(
            and_(
                func.date(AnalyticsRecord.checkout_date) >= start_date,
                func.date(AnalyticsRecord.checkout_date) <= end_date
            )
        )
        if waiter_id:
            period_summary_query = period_summary_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        period_summary = period_summary_query.first()
        
        return {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'summary': {
                'total_orders': period_summary.total_orders or 0,
                'total_revenue': float(period_summary.total_revenue or 0),
                'unique_items_sold': period_summary.unique_items or 0,
                'top_items_count': len(items_data)
            },
            'top_items': items_data
        }
        
    except Exception as e:
        return {
            'period': period,
            'error': str(e),
            'summary': {'total_orders': 0, 'total_revenue': 0, 'unique_items_sold': 0},
            'top_items': []
        }

def get_item_performance_trends(db: Session, item_name: str, days: int = 30, restaurant_id: int = None) -> Dict:
    """Get performance trends for a specific item over time"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Daily performance for the item
        daily_data = db.query(
            func.date(AnalyticsRecord.checkout_date).label('date'),
            func.sum(AnalyticsRecord.quantity).label('quantity'),
            func.sum(AnalyticsRecord.total_price).label('revenue'),
            func.count(func.distinct(AnalyticsRecord.checkout_date)).label('orders')
        ).filter(
            and_(
                AnalyticsRecord.item_name == item_name,
                func.date(AnalyticsRecord.checkout_date) >= start_date,
                func.date(AnalyticsRecord.checkout_date) <= end_date
            )
        ).group_by(
            func.date(AnalyticsRecord.checkout_date)
        ).order_by(
            func.date(AnalyticsRecord.checkout_date)
        ).all()
        
        # Fill missing dates with zeros
        trends = []
        current_date = start_date
        daily_dict = {str(row.date): row for row in daily_data}
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            if date_str in daily_dict:
                row = daily_dict[date_str]
                trends.append({
                    'date': date_str,
                    'quantity': row.quantity,
                    'revenue': float(row.revenue),
                    'orders': row.orders
                })
            else:
                trends.append({
                    'date': date_str,
                    'quantity': 0,
                    'revenue': 0.0,
                    'orders': 0
                })
            current_date += timedelta(days=1)
        
        # Calculate summary stats
        total_quantity = sum(t['quantity'] for t in trends)
        total_revenue = sum(t['revenue'] for t in trends)
        active_days = len([t for t in trends if t['quantity'] > 0])
        
        return {
            'item_name': item_name,
            'period_days': days,
            'summary': {
                'total_quantity': total_quantity,
                'total_revenue': total_revenue,
                'active_days': active_days,
                'avg_daily_quantity': total_quantity / days if days > 0 else 0,
                'avg_daily_revenue': total_revenue / days if days > 0 else 0
            },
            'daily_trends': trends
        }
        
    except Exception as e:
        return {
            'item_name': item_name,
            'error': str(e),
            'summary': {'total_quantity': 0, 'total_revenue': 0, 'active_days': 0},
            'daily_trends': []
        }

def get_category_comparison(db: Session, period: str = "month", target_date: str = None, waiter_id: int = None, restaurant_id: int = None) -> Dict:
    """Compare performance across categories"""
    try:
        if target_date is None:
            target_date_obj = date.today()
        else:
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        
        # Calculate date range
        if period == "day":
            start_date = target_date_obj
            end_date = target_date_obj
        elif period == "week":
            start_date = target_date_obj - timedelta(days=target_date_obj.weekday())
            end_date = start_date + timedelta(days=6)
        elif period == "month":
            start_date = target_date_obj.replace(day=1)
            if target_date_obj.month == 12:
                next_month = target_date_obj.replace(year=target_date_obj.year + 1, month=1)
            else:
                next_month = target_date_obj.replace(month=target_date_obj.month + 1)
            end_date = next_month - timedelta(days=1)
        elif period == "year":
            start_date = target_date_obj.replace(month=1, day=1)
            end_date = target_date_obj
        
        # Category performance
        categories_query = db.query(
            AnalyticsRecord.item_category,
            func.sum(AnalyticsRecord.quantity).label('total_quantity'),
            func.sum(AnalyticsRecord.total_price).label('total_revenue'),
            func.count(func.distinct(AnalyticsRecord.item_name)).label('unique_items'),
            func.count(func.distinct(AnalyticsRecord.checkout_date)).label('orders_count'),
            func.avg(AnalyticsRecord.unit_price).label('avg_item_price')
        ).filter(
            and_(
                func.date(AnalyticsRecord.checkout_date) >= start_date,
                func.date(AnalyticsRecord.checkout_date) <= end_date
            )
        )
        if waiter_id:
            categories_query = categories_query.filter(AnalyticsRecord.waiter_id == waiter_id)
        categories = categories_query.group_by(
            AnalyticsRecord.item_category
        ).order_by(
            desc(func.sum(AnalyticsRecord.total_price))
        ).all()
        
        # Calculate totals for percentages
        total_revenue = sum(float(cat.total_revenue) for cat in categories)
        total_quantity = sum(cat.total_quantity for cat in categories)
        
        categories_data = []
        for cat in categories:
            revenue = float(cat.total_revenue)
            categories_data.append({
                'category': cat.item_category,
                'quantity_sold': cat.total_quantity,
                'revenue': revenue,
                'unique_items': cat.unique_items,
                'orders_count': cat.orders_count,
                'avg_item_price': float(cat.avg_item_price),
                'revenue_percentage': (revenue / total_revenue * 100) if total_revenue > 0 else 0,
                'quantity_percentage': (cat.total_quantity / total_quantity * 100) if total_quantity > 0 else 0,
                'avg_revenue_per_order': revenue / max(cat.orders_count, 1)
            })
        
        return {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'summary': {
                'total_categories': len(categories_data),
                'total_revenue': total_revenue,
                'total_quantity': total_quantity
            },
            'categories': categories_data
        }
        
    except Exception as e:
        return {
            'period': period,
            'error': str(e),
            'summary': {'total_categories': 0, 'total_revenue': 0, 'total_quantity': 0},
            'categories': []
        }