let menu = [];
let order = [];
let roomNumber = null;
let roomCode = '';

document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    roomNumber = urlParams.get('room');
    
    if (roomNumber) {
        document.getElementById('room-number').textContent = roomNumber;
        document.getElementById('room-number-input').value = roomNumber;
        loadMenu();
        loadExistingOrder();
    } else {
        showMessage('Please specify a room number in the URL (?room=X)', 'error');
    }
    
    document.getElementById('order-form').addEventListener('submit', placeOrder);
});

async function loadMenu() {
    try {
        const response = await fetch(`/client/menu?room=${roomNumber}`);
        const data = await response.json();
        
        if (response.ok) {
            menu = data.menu;
            roomCode = data.room_code;
            displayMenu();
            document.getElementById('menu-section').style.display = 'block';
        } else {
            showMessage(data.detail || 'Error loading menu', 'error');
        }
    } catch (error) {
        showMessage('Error connecting to server', 'error');
    }
}

function displayMenu() {
    const menuContainer = document.getElementById('menu-items');
    menuContainer.innerHTML = '';
    
    // Display menu by categories
    Object.keys(menu).forEach(category => {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'menu-category';
        categoryDiv.innerHTML = `<h3 class="category-title">${category}</h3>`;
        
        const categoryItems = document.createElement('div');
        categoryItems.className = 'category-items';
        
        menu[category].forEach(item => {
            const menuItemDiv = document.createElement('div');
            menuItemDiv.className = 'menu-item';
            menuItemDiv.innerHTML = `
                <h4>${item.name}</h4>
                <p class="ingredients">${item.ingredients || 'No ingredients listed'}</p>
                <p class="price">€${item.price.toFixed(2)}</p>
                <div class="quantity-controls">
                    <button type="button" onclick="updateQuantity(${item.id}, -1)">-</button>
                    <span id="qty-${item.id}">0</span>
                    <button type="button" onclick="updateQuantity(${item.id}, 1)">+</button>
                </div>
            `;
            categoryItems.appendChild(menuItemDiv);
        });
        
        categoryDiv.appendChild(categoryItems);
        menuContainer.appendChild(categoryDiv);
    });
}

function updateQuantity(itemId, change) {
    const qtyElement = document.getElementById(`qty-${itemId}`);
    let currentQty = parseInt(qtyElement.textContent);
    let newQty = Math.max(0, currentQty + change);
    
    qtyElement.textContent = newQty;
    
    // Update order array
    const existingItem = order.find(item => item.product_id === itemId);
    if (existingItem) {
        if (newQty === 0) {
            order = order.filter(item => item.product_id !== itemId);
        } else {
            existingItem.qty = newQty;
        }
    } else if (newQty > 0) {
        order.push({ product_id: itemId, qty: newQty });
    }
    
    updateOrderDisplay();
}

function updateOrderDisplay() {
    const orderItemsContainer = document.getElementById('order-items');
    const totalElement = document.getElementById('total');
    const placeOrderBtn = document.getElementById('place-order-btn');
    
    orderItemsContainer.innerHTML = '';
    let total = 0;
    
    order.forEach(orderItem => {
        let menuItem = null;
        // Find item in categorized menu
        Object.values(menu).forEach(categoryItems => {
            const found = categoryItems.find(item => item.id === orderItem.product_id);
            if (found) menuItem = found;
        });
        
        if (menuItem) {
            const itemTotal = menuItem.price * orderItem.qty;
            total += itemTotal;
            
            const orderItemDiv = document.createElement('div');
            orderItemDiv.className = 'order-item';
            orderItemDiv.innerHTML = `
                <span>${menuItem.name} x${orderItem.qty}</span>
                <span>€${itemTotal.toFixed(2)}</span>
            `;
            orderItemsContainer.appendChild(orderItemDiv);
        }
    });
    
    totalElement.textContent = `Total: €${total.toFixed(2)}`;
    placeOrderBtn.disabled = order.length === 0;
}

async function placeOrder(event) {
    event.preventDefault();
    
    const code = document.getElementById('room-code').value;
    if (code.length !== 3) {
        showMessage('Please enter a valid 3-digit code', 'error');
        return;
    }
    
    if (order.length === 0) {
        showMessage('Please select at least one item', 'error');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('room_number', roomNumber);
        formData.append('code', code);
        formData.append('items', JSON.stringify(order));
        
        const response = await fetch('/client/order', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage(data.message, 'success');
            // Reset form
            order = [];
            document.getElementById('order-form').reset();
            document.querySelectorAll('[id^="qty-"]').forEach(el => el.textContent = '0');
            updateOrderDisplay();
            // Reload to show updated order
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showMessage(data.detail || 'Error placing order', 'error');
        }
    } catch (error) {
        showMessage('Error connecting to server', 'error');
    }
}

async function loadExistingOrder() {
    try {
        const response = await fetch(`/client/order_details/${roomNumber}`);
        const data = await response.json();
        
        if (data.has_order) {
            displayExistingOrder(data);
        }
    } catch (error) {
        console.error('Error loading existing order:', error);
    }
}

function displayExistingOrder(orderData) {
    const existingOrderDiv = document.createElement('div');
    existingOrderDiv.id = 'existing-order';
    existingOrderDiv.innerHTML = `
        <h3>Current Room Service Order</h3>
        <div class="existing-order-items">
            ${orderData.items.map(item => `
                <div class="existing-order-item">
                    <span>${item.name} x${item.qty}</span>
                    <span>€${item.total.toFixed(2)}</span>
                </div>
            `).join('')}
        </div>
        <div class="existing-order-total">Total: €${orderData.total.toFixed(2)}</div>
        <p id="order-status-message"><em>Your order is being prepared. You can add more items below.</em></p>
    `;
    
    const menuSection = document.getElementById('menu-section');
    menuSection.insertBefore(existingOrderDiv, menuSection.firstChild);
}

function showMessage(message, type) {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = message;
    messageDiv.className = type;
    messageDiv.style.display = 'block';
    
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}