# Multi-Tenant TableLink - Test Guide

## 🎉 Multi-Tenant Setup Complete!

Your TableLink system now supports multiple restaurants with separate data, plans, and features.

## Test URLs (Development)

Since we're testing locally, use these URLs to access different restaurants:

### 1. Demo Restaurant (Professional Plan - Trial)
- **URL**: `http://localhost:8000/business`
- **Login**: admin / rrares
- **Features**: ✅ Full analytics, ✅ Advanced features

### 2. Mario's Pizza (Basic Plan - Trial)  
- **URL**: `http://localhost:8000/r/marios/business`
- **Login**: admin / ueApVg6A
- **Features**: ✅ Basic dashboard, ❌ Advanced analytics (shows upgrade page)

### 3. Sushi Express (Professional Plan - Trial)
- **URL**: `http://localhost:8000/r/sushi/business`  
- **Login**: admin / vsMtMJgT
- **Features**: ✅ Full analytics, ✅ Advanced features

## What to Test

### ✅ Data Isolation
1. Create orders in Mario's Pizza
2. Check that Demo Restaurant doesn't see Mario's orders
3. Verify each restaurant has separate menus, waiters, tables

### ✅ Plan-Based Features
1. **Mario's Pizza (Basic)**: Try accessing `/business/analytics` → Should show upgrade page
2. **Demo/Sushi (Professional)**: Should have full analytics access

### ✅ Customer Ordering
- **Demo**: `http://localhost:8000/table/1` (code: 123)
- **Mario's**: `http://localhost:8000/r/marios/table/1` (code: 123)  
- **Sushi**: `http://localhost:8000/r/sushi/table/1` (code: 123)

## Restaurant Management Commands

```bash
# List all restaurants
python restaurant_admin.py list

# Create new restaurant
python restaurant_admin.py create "New Restaurant" "subdomain" "basic"

# Upgrade restaurant plan
python restaurant_admin.py upgrade 2 professional
```

## Production Deployment Notes

For production with real subdomains:
- **Demo**: `http://demo.tablelink.com`
- **Mario's**: `http://marios.tablelink.com`
- **Sushi**: `http://sushi.tablelink.com`

## Revenue Potential (Current Setup)

With 3 restaurants:
- Mario's: $49/month (Basic)
- Demo: $79/month (Professional) 
- Sushi: $79/month (Professional)
- **Total**: $207/month
- **Infrastructure cost**: ~$14/month
- **Net profit**: $193/month (93% margin)

## Next Steps for Production

1. **Deploy to Heroku**: `git push heroku main`
2. **Setup custom domain**: tablelink.com
3. **Configure DNS**: Wildcard subdomain (*.tablelink.com)
4. **Stripe integration**: Payment processing
5. **Email notifications**: Trial expiry, billing

## 🚀 Ready for Sales!

Your multi-tenant system is ready. You can now:
1. Visit restaurants in person
2. Create accounts on-the-spot
3. Give 5-day trials
4. Convert to paid plans

**Break-even**: Just 1 restaurant covers all costs!