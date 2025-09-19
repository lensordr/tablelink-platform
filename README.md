# Restaurant Management System

A complete restaurant application with client ordering and business management features.

## Features

### Client Features (/client?table=X)
- View active menu items from database
- Select products and quantities
- Enter 3-digit table code to place order
- Real-time order total calculation

### Business Features (/business)
- Dashboard with table status (gray=free, green=occupied)
- Click occupied tables to view order details
- Finish tables to free them up
- Upload Excel/PDF files to import menu items
- Toggle product active/inactive status
- Real-time dashboard updates

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

3. Access the application:
- Client: http://localhost:8000/client?table=1
- Business: http://localhost:8000/business

## Database Schema

- **Tables**: table_number (PK), code (3-digit), status
- **MenuItems**: id (PK), name, ingredients, price, active
- **Orders**: id (PK), table_number (FK), created_at, status
- **OrderItems**: id (PK), order_id (FK), product_id (FK), qty

## File Upload Format

### Excel Files
Columns: name, ingredients, price

### PDF Files
Format: "Item Name - $Price - Ingredients" per line

## Testing with ngrok

1. Install ngrok
2. Run: `ngrok http 8000`
3. Use the provided URL to access from mobile devices

## Sample Table Codes
- Table 1: 123
- Table 2: 456
- Table 3: 789
- Table 4: 321
- Table 5: 654
- Table 6: 987
- Table 7: 147
- Table 8: 258
- Table 9: 369
- Table 10: 741