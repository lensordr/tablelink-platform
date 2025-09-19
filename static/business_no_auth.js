let tables = [];
let menuItems = [];

// Sound alerts
const newOrderSound = new Audio('/static/sounds/new-order.mp3');
const checkoutSound = new Audio('/static/sounds/checkout-request.mp3');

// Track previous state for sound alerts
let previousTables = [];

// Track notifications
let notificationCount = 0;
let currentSection = 'live-orders';

document.addEventListener('DOMContentLoaded', function() {
    currentDate = new Date().toISOString().split('T')[0];
    currentSection = 'live-orders';
    showSection('live-orders');
    
    document.getElementById('upload-form').addEventListener('submit', uploadMenu);
    
    // Modal controls
    const modal = document.getElementById('order-modal');
    const closeBtn = document.querySelector('.close');
    
    closeBtn.onclick = function() {
        closeModal();
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            closeModal();
        }
    }
    
    document.getElementById('checkout-table-btn').addEventListener('click', finishTable);
    
    // Load waiters for modal
    loadWaitersForModal();
    
    // Auto-refresh dashboard every 3 seconds
    setInterval(loadDashboard, 3000);
    
    // Check trial status every 30 seconds
    setInterval(checkTrialStatus, 30000);
    
    // Initialize app
    loadDashboard();
    loadMenuItems();
    loadSales('day');
    loadWaiters();
    checkTrialStatus();
});

let currentTableNumber = null;

async function closeModal() {
    const modal = document.getElementById('order-modal');
    
    // Mark order as viewed when closing modal
    if (currentTableNumber) {
        try {
            console.log(`Marking table ${currentTableNumber} as viewed`);
            const response = await fetch(`/business/mark_viewed/${currentTableNumber}`, {
                method: 'POST'
            });
            if (response.ok) {
                console.log('Order marked as viewed successfully');
            }
        } catch (error) {
            console.error('Error marking order as viewed:', error);
        }
    }
    
    modal.style.display = 'none';
    currentTableNumber = null;
}

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json'
    };
}

function logout() {
    // Preserve restaurant context in logout redirect
    const currentPath = window.location.pathname;
    console.log('Logout: current path =', currentPath);
    alert('Logout clicked! Current path: ' + currentPath);
    
    if (currentPath.includes('/r/')) {
        // Extract subdomain from current path
        const pathParts = currentPath.split('/');
        const subdomain = pathParts[2];
        const redirectUrl = `/r/${subdomain}/business/login`;
        console.log('Logout: redirecting to', redirectUrl);
        alert('Redirecting to: ' + redirectUrl);
        window.location.href = redirectUrl;
    } else {
        console.log('Logout: no /r/ in path, using default redirect');
        alert('No /r/ in path, using default redirect');
        window.location.href = '/business/login';
    }
}

async function loadDashboard() {
    try {
        const url = '/business/tables';
        console.log('Current URL:', window.location.href);
        console.log('Loading dashboard from:', url);
        
        const response = await fetch(url);
        console.log('Response status:', response.status);
        console.log('Response URL:', response.url);
        console.log('Response headers:', response.headers.get('content-type'));
        
        if (!response.ok) {
            console.error('Response not OK:', response.status, response.statusText);
            const text = await response.text();
            console.error('Response body:', text.substring(0, 200));
            return;
        }
        
        const text = await response.text();
        console.log('Raw response:', text.substring(0, 100));
        
        const data = JSON.parse(text);
        console.log('Tables data received:', data);
        
        // Check for sound alerts before updating tables
        checkForSoundAlerts(data);
        
        tables = data;
        displayTables();
        console.log('Tables set:', tables.length, 'tables');
        
        // Update previous state
        previousTables = JSON.parse(JSON.stringify(data));
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function checkForSoundAlerts(currentTables) {
    if (previousTables.length === 0) {
        previousTables = JSON.parse(JSON.stringify(currentTables));
        return;
    }
    
    let newNotifications = 0;
    
    currentTables.forEach(currentTable => {
        const previousTable = previousTables.find(t => t.table_number === currentTable.table_number);
        
        if (previousTable) {
            // Check for new orders or extra orders
            if ((currentTable.status === 'occupied' && previousTable.status === 'free') ||
                (currentTable.has_extra_order && !previousTable.has_extra_order)) {
                try {
                    newOrderSound.play().catch(e => console.log('Sound play failed:', e));
                } catch (e) {
                    console.log('Sound not available');
                }
                
                // Add notification if not on live orders tab
                if (currentSection !== 'live-orders') {
                    newNotifications++;
                    console.log(`New order notification added for table ${currentTable.table_number}`);
                }
            }
            
            // Check for checkout requests
            if (currentTable.checkout_requested && !previousTable.checkout_requested) {
                try {
                    checkoutSound.play().catch(e => console.log('Sound play failed:', e));
                } catch (e) {
                    console.log('Sound not available');
                }
                
                // Add notification if not on live orders tab
                if (currentSection !== 'live-orders') {
                    newNotifications++;
                    console.log(`Checkout notification added for table ${currentTable.table_number}`);
                }
            }
        }
    });
    
    // Update notification count
    if (newNotifications > 0) {
        notificationCount += newNotifications;
        console.log(`Total notifications: ${notificationCount}`);
        updateNotificationBadge();
    }
}

function displayTables() {
    const tablesGrid = document.getElementById('tables-grid');
    if (!tablesGrid) {
        console.error('tables-grid element not found!');
        return;
    }
    
    console.log('Displaying', tables.length, 'tables');
    tablesGrid.innerHTML = '';
    
    tables.forEach(table => {
        const tableCard = document.createElement('div');
        let cardClass = `table-card ${table.status}`;
        
        if (table.checkout_requested) {
            cardClass += ' checkout-requested';
            tableCard.setAttribute('data-checkout-method', table.checkout_method);
        } else if (table.has_extra_order) {
            cardClass += ' extra-order';
            console.log(`Table ${table.table_number} has extra order - adding red styling`);
        }
        
        tableCard.className = cardClass;
        tableCard.innerHTML = `
            <div>Table ${table.table_number}</div>
            <div style="font-size: 12px; margin-top: 5px;">Code: ${table.code}</div>
        `;
        
        if (table.status === 'occupied') {
            tableCard.onclick = () => showOrderDetails(table.table_number);
        }
        
        tablesGrid.appendChild(tableCard);
    });
    
    console.log('Tables displayed successfully');
}

async function showOrderDetails(tableNumber) {
    // Switch to live-orders section first
    showSection('live-orders');
    
    try {
        const response = await fetch(`/business/order_details/${tableNumber}`);
        const data = await response.json();
        
        // Find table data for tip information
        const table = tables.find(t => t.table_number === tableNumber);
        
        if (response.ok) {
            currentTableNumber = tableNumber;
            console.log(`Opening modal for table ${tableNumber}`);
            
            document.getElementById('modal-table-number').textContent = tableNumber;
            
            const orderDetailsDiv = document.getElementById('order-details');
            orderDetailsDiv.innerHTML = `
                <p><strong>Order ID:</strong> ${data.order_id}</p>
                <p><strong>Order Time:</strong> ${new Date(data.created_at).toLocaleString()}</p>
                <h3>Items:</h3>
                <div class="order-items">
                    ${data.items.map(item => {
                        let customizationText = '';
                        if (item.customizations) {
                            try {
                                const custom = JSON.parse(item.customizations);
                                const customParts = [];
                                
                                if (custom.ingredients) {
                                    Object.entries(custom.ingredients).forEach(([ing, qty]) => {
                                        if (qty === 0) {
                                            customParts.push(`No ${ing}`);
                                        } else if (qty > 1) {
                                            customParts.push(`Extra ${ing} X${qty}`);
                                        }
                                    });
                                }
                                
                                if (custom.extra && custom.extra.length > 0) {
                                    customParts.push(`Add: ${custom.extra.join(', ')}`);
                                }
                                
                                if (custom.removed && custom.removed.length > 0) {
                                    customParts.push(`No: ${custom.removed.join(', ')}`);
                                }
                                if (custom.added && custom.added.length > 0) {
                                    customParts.push(`Extra: ${custom.added.join(', ')}`);
                                }
                                
                                if (customParts.length > 0) {
                                    customizationText = `<br><small style="color: #666; font-style: italic;">${customParts.join(' | ')}</small>`;
                                }
                            } catch (e) {
                                console.error('Error parsing customizations:', e);
                            }
                        }
                        
                        return `
                            <div class="order-detail-item">
                                <span>
                                    ${item.name} x${item.qty}
                                    ${item.is_new_extra ? '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color: red; font-weight: bold;">NEW</span>' : ''}
                                    ${customizationText}
                                </span>
                                <span>€${item.total.toFixed(2)}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
                <div style="margin-top: 15px; font-size: 18px; font-weight: bold;">
                    Subtotal: €${data.total.toFixed(2)}<br>
                    Tip: €${(table.tip_amount || 0).toFixed(2)}<br>
                    <div style="border-top: 1px solid #ccc; padding-top: 5px; margin-top: 5px;">
                        Total to Charge: €${(data.total + (table.tip_amount || 0)).toFixed(2)}
                    </div>
                </div>
            `;
            
            document.getElementById('checkout-table-btn').setAttribute('data-table', tableNumber);
            document.getElementById('order-modal').style.display = 'block';
        }
    } catch (error) {
        showMessage('Error loading order details', 'error');
    }
}

async function finishTable() {
    const tableNumber = document.getElementById('checkout-table-btn').getAttribute('data-table');
    const waiterId = document.getElementById('waiter-select').value;
    
    if (!waiterId) {
        showMessage('Please select a waiter', 'error');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('waiter_id', waiterId);
        
        const response = await fetch(`/business/checkout_table/${tableNumber}`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Table checkout completed successfully', 'success');
            closeModal();
            await loadDashboard();
        } else {
            showMessage(data.detail || 'Error processing checkout', 'error');
        }
    } catch (error) {
        showMessage('Error connecting to server', 'error');
    }
}

async function loadMenuItems() {
    try {
        const response = await fetch('/business/menu_items');
        const data = await response.json();
        
        if (response.ok) {
            menuItems = data.items;
            displayMenuItems();
        }
    } catch (error) {
        console.error('Error loading menu items:', error);
    }
}

function displayMenuItems() {
    const menuItemsList = document.getElementById('menu-items-list');
    menuItemsList.innerHTML = '';
    
    menuItems.forEach(item => {
        const itemRow = document.createElement('div');
        itemRow.className = 'menu-item-row';
        itemRow.innerHTML = `
            <div class="menu-item-info">
                <div class="menu-item-name">${item.name}</div>
                <div class="menu-item-price">€${item.price.toFixed(2)}</div>
                <div style="font-size: 12px; color: #666;">${item.ingredients}</div>
            </div>
            <button class="toggle-btn ${item.active ? 'active' : 'inactive'}" 
                    onclick="toggleProduct(${item.id})">
                ${item.active ? 'Active' : 'Inactive'}
            </button>
        `;
        menuItemsList.appendChild(itemRow);
    });
}

async function toggleProduct(productId) {
    try {
        const response = await fetch(`/business/toggle_product/${productId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage(data.message, 'success');
            loadMenuItems();
        } else {
            showMessage(data.detail || 'Error toggling product', 'error');
        }
    } catch (error) {
        showMessage('Error connecting to server', 'error');
    }
}

async function uploadMenu(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('menu-file');
    const file = fileInput.files[0];
    
    if (!file) {
        showMessage('Please select a file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('menu_file', file);
    
    try {
        const response = await fetch('/business/menu/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Menu uploaded successfully', 'success');
            fileInput.value = '';
            loadMenuItems();
        } else {
            showMessage(data.detail || 'Error uploading menu', 'error');
        }
    } catch (error) {
        showMessage('Error connecting to server', 'error');
    }
}

let currentPeriod = 'day';
let currentDate = new Date().toISOString().split('T')[0];
let currentWaiterId = null;
let showOverall = false;

async function loadSales(period) {
    currentPeriod = period;
    currentDate = new Date().toISOString().split('T')[0];
    
    console.log(`Loading sales for period: ${period}, date: ${currentDate}`);
    try {
        let url = `/business/sales?period=${period}&target_date=${currentDate}`;
        if (currentWaiterId) {
            url += `&waiter_id=${currentWaiterId}`;
        }
        console.log(`Fetching: ${url}`);
        const response = await fetch(url);
        const data = await response.json();
        console.log(`Sales data received:`, data);
        
        if (response.ok) {
            displaySalesData(data);
            updatePeriodButtons(period);
        }
    } catch (error) {
        console.error('Error loading sales:', error);
        // Clear data on error
        displaySalesData({summary: {total_orders: 0, total_sales: 0, total_tips: 0}, waiters: []});
    }
}

async function loadTopItems() {
    try {
        console.log(`Loading top items for period: ${currentPeriod}`);
        const response = await fetch(`/business/top-menu-items?period=${currentPeriod}&limit=5&_t=${Date.now()}`);
        const data = await response.json();
        console.log('Top items response:', data);
        
        if (data.items && data.items.length > 0) {
            const container = document.getElementById('top-items-list');
            container.innerHTML = data.items.map((item, index) => `
                <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee;">
                    <div>
                        <span style="color: #007bff; font-weight: bold;">#${index + 1}</span>
                        <span style="margin-left: 8px;">${item.name}</span>
                    </div>
                    <div style="text-align: right; font-size: 12px;">
                        <div><strong>${item.quantity}</strong> sold</div>
                        <div style="color: #666;">€${item.revenue.toFixed(2)}</div>
                    </div>
                </div>
            `).join('');
        } else {
            document.getElementById('top-items-list').innerHTML = '<p style="color: #666; font-size: 12px; margin: 0;">No sales data yet</p>';
        }
    } catch (error) {
        console.error('Error loading top items:', error);
        document.getElementById('top-items-list').innerHTML = '<p style="color: #666; font-size: 12px; margin: 0;">Error loading data</p>';
    }
}

function displaySalesData(data) {
    const summaryDiv = document.getElementById('sales-summary');
    
    summaryDiv.innerHTML = `
        <div class="sales-summary-cards">
            <div class="summary-card">
                <h4>💰 Total Sales</h4>
                <div class="summary-value">€${data.summary.total_sales.toFixed(2)}</div>
            </div>
            <div class="summary-card">
                <h4>🎯 Total Orders</h4>
                <div class="summary-value">${data.summary.total_orders}</div>
            </div>
            <div class="summary-card">
                <h4>💡 Total Tips</h4>
                <div class="summary-value">€${data.summary.total_tips.toFixed(2)}</div>
            </div>
        </div>
    `;
}

function updatePeriodButtons(activePeriod) {
    document.querySelectorAll('.period-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`${activePeriod}-btn`).classList.add('active');
}

function showSection(sectionName) {
    console.log('Showing section:', sectionName);
    currentSection = sectionName;
    
    // Debug: Check if QR codes section exists
    if (sectionName === 'qr-codes') {
        const qrSection = document.getElementById('qr-codes');
        console.log('QR codes section found:', !!qrSection);
        if (!qrSection) {
            console.error('QR codes section not found in DOM!');
            return;
        }
    }
    
    document.querySelectorAll('.section-content').forEach(section => {
        section.style.display = 'none';
    });
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(sectionName).style.display = 'block';
    document.getElementById(sectionName + '-btn').classList.add('active');
    
    // Clear notifications when viewing live orders
    if (sectionName === 'live-orders') {
        console.log('Clearing notifications - switched to live orders');
        clearNotifications();
        loadDashboard();
    } else if (sectionName === 'analytics') {
        loadSales(currentPeriod);
    } else if (sectionName === 'menu-management') {
        loadMenuItems();
    } else if (sectionName === 'waiters-new') {
        loadWaiters();
    } else if (sectionName === 'qr-codes') {
        openQRCodesWindow();
    }
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

async function loadWaiters() {
    try {
        const response = await fetch('/business/waiters');
        const data = await response.json();
        
        if (response.ok) {
            showWaiters(data.waiters);
        }
    } catch (error) {
        console.error('Error:', error);
        showWaiters([]);
    }
}

function showWaiters(waiters) {
    const container = document.getElementById('waiters-container');
    
    if (waiters.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px; background: #f7fafc; border-radius: 8px;">No waiters yet. Add one above!</p>';
        return;
    }
    
    container.innerHTML = waiters.map(w => `
        <div style="background: white; padding: 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; border: 2px solid #e2e8f0;">
            <span style="font-weight: 600; color: #2d3748;">${w.name}</span>
            <button onclick="removeWaiter(${w.id})" style="background: #e53e3e; color: white; border: none; padding: 8px 15px; border-radius: 6px; cursor: pointer;">Delete</button>
        </div>
    `).join('');
}

async function addWaiter() {
    const input = document.getElementById('waiter-input');
    const name = input.value.trim();
    
    if (!name) {
        alert('Please enter a name');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('name', name);
        
        const response = await fetch('/business/waiters', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            input.value = '';
            loadWaiters();
            loadWaitersForModal();
            showMessage('Waiter added!', 'success');
        }
    } catch (error) {
        alert('Error adding waiter');
    }
}

async function removeWaiter(id) {
    if (!confirm('Delete this waiter?')) return;
    
    try {
        const response = await fetch(`/business/waiters/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadWaiters();
            loadWaitersForModal();
            showMessage('Waiter deleted!', 'success');
        }
    } catch (error) {
        alert('Error deleting waiter');
    }
}

async function loadWaitersForModal() {
    try {
        const response = await fetch('/business/waiters');
        const data = await response.json();
        
        if (response.ok) {
            const select = document.getElementById('waiter-select');
            select.innerHTML = '<option value="">Choose waiter...</option>';
            data.waiters.forEach(waiter => {
                const option = document.createElement('option');
                option.value = waiter.id;
                option.textContent = waiter.name;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading waiters for modal:', error);
    }
}

function updateNotificationBadge() {
    const liveOrdersBtn = document.getElementById('live-orders-btn');
    
    console.log(`Updating notifications: hasNotifications=${notificationCount > 0}, section=${currentSection}`);
    
    if (notificationCount > 0 && currentSection !== 'live-orders') {
        liveOrdersBtn.classList.add('has-notifications');
        console.log('Button blinking started');
    } else {
        liveOrdersBtn.classList.remove('has-notifications');
        console.log('Button blinking stopped');
    }
}

function clearNotifications() {
    console.log('Clearing all notifications');
    notificationCount = 0;
    const liveOrdersBtn = document.getElementById('live-orders-btn');
    liveOrdersBtn.classList.remove('has-notifications');
}

async function checkTrialStatus() {
    try {
        const response = await fetch('/business/trial-status');
        const data = await response.json();
        
        if (data.show_warning) {
            showTrialWarning(data.days_left);
        } else {
            hideTrialWarning();
        }
    } catch (error) {
        console.error('Error checking trial status:', error);
    }
}

function showTrialWarning(daysLeft) {
    let warningDiv = document.getElementById('trial-warning');
    if (!warningDiv) {
        warningDiv = document.createElement('div');
        warningDiv.id = 'trial-warning';
        warningDiv.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            padding: 15px;
            text-align: center;
            z-index: 1000;
            font-weight: bold;
            color: #856404;
        `;
        document.body.insertBefore(warningDiv, document.body.firstChild);
    }
    
    warningDiv.innerHTML = `
        ⚠️ Trial expires in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}! 
        <a href="mailto:lens.ordr@gmail.com" style="color: #007bff; margin-left: 10px;">Upgrade Now</a>
        <button onclick="hideTrialWarning()" style="float: right; background: none; border: none; font-size: 18px; cursor: pointer;">×</button>
    `;
}

function hideTrialWarning() {
    const warningDiv = document.getElementById('trial-warning');
    if (warningDiv) {
        warningDiv.remove();
    }
}

async function loadQRCodes() {
    try {
        console.log('Loading QR codes...');
        const response = await fetch('/business/qr-codes');
        const data = await response.json();
        
        console.log('QR codes response:', data);
        
        if (response.ok && data.qr_codes) {
            console.log('Displaying', data.qr_codes.length, 'QR codes');
            displayQRCodes(data.qr_codes);
        } else {
            console.error('No QR codes data received');
        }
    } catch (error) {
        console.error('Error loading QR codes:', error);
    }
}

function displayQRCodes(qrCodes) {
    const grid = document.getElementById('qr-codes-grid');
    grid.innerHTML = '';
    
    qrCodes.forEach(qrData => {
        const qrCard = document.createElement('div');
        qrCard.style.cssText = `
            background: white;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        `;
        
        qrCard.innerHTML = `
            <h3 style="margin: 0 0 15px 0; color: #333;">Table ${qrData.table_number}</h3>
            <div id="qr-${qrData.table_number}" style="margin: 15px 0;"></div>
            <p style="font-size: 12px; color: #666; margin: 10px 0;">Code: ${qrData.code}</p>
            <p style="font-size: 11px; color: #888; word-break: break-all; margin: 10px 0;">${qrData.url}</p>
            <button onclick="printQRCode(${qrData.table_number})" style="background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 10px;">🖨️ Print</button>
        `;
        
        grid.appendChild(qrCard);
        
        // Generate QR code - with fallback if library not loaded
        const qrContainer = document.getElementById(`qr-${qrData.table_number}`);
        
        if (typeof QRCode !== 'undefined') {
            QRCode.toCanvas(qrContainer, qrData.url, {
                width: 200,
                margin: 2,
                color: {
                    dark: '#000000',
                    light: '#FFFFFF'
                }
            }, function (error) {
                if (error) console.error('QR Code generation error:', error);
            });
        } else {
            // Fallback: Use Google Charts QR API
            const qrImg = document.createElement('img');
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrData.url)}`;
            qrImg.src = qrUrl;
            qrImg.style.cssText = 'width: 200px; height: 200px; border: 2px solid #ddd;';
            qrContainer.appendChild(qrImg);
        }
    });
}

function printQRCode(tableNumber) {
    const qrCanvas = document.querySelector(`#qr-${tableNumber} canvas`);
    if (!qrCanvas) return;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
            <head>
                <title>Table ${tableNumber} QR Code</title>
                <style>
                    body { text-align: center; font-family: Arial, sans-serif; margin: 50px; }
                    h1 { margin-bottom: 30px; }
                    canvas { border: 2px solid #ddd; }
                    p { margin-top: 20px; font-size: 14px; color: #666; }
                </style>
            </head>
            <body>
                <h1>Table ${tableNumber}</h1>
                ${qrCanvas.outerHTML}
                <p>Scan to view menu and place orders</p>
            </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
}

function openQRCodesWindow() {
    const qrWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes');
    
    fetch('/business/qr-codes')
        .then(response => response.json())
        .then(data => {
            let windowContent = `
                <html>
                    <head>
                        <title>QR Codes - Restaurant Tables</title>
                        <style>
                            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                            h1 { text-align: center; color: #333; margin-bottom: 30px; }
                            .qr-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
                            .qr-card { background: white; border: 2px solid #e2e8f0; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                            .qr-card h3 { margin: 0 0 15px 0; color: #333; }
                            .qr-code { margin: 15px 0; }
                            .table-info { font-size: 12px; color: #666; margin: 10px 0; }
                            .table-url { font-size: 11px; color: #888; word-break: break-all; }
                            .print-btn { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-top: 10px; }
                            .print-all { text-align: center; margin: 20px 0; }
                            .print-all button { background: #28a745; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 16px; }
                        </style>
                    </head>
                    <body>
                        <h1>📱 QR Codes for Restaurant Tables</h1>
                        <div class="print-all">
                            <button onclick="window.print()">🖨️ Print All QR Codes</button>
                        </div>
                        <div class="qr-grid">
            `;
            
            data.qr_codes.forEach(qrData => {
                const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrData.url)}`;
                windowContent += `
                    <div class="qr-card">
                        <h3>Table ${qrData.table_number}</h3>
                        <div class="qr-code">
                            <img src="${qrUrl}" alt="QR Code for Table ${qrData.table_number}" style="width: 200px; height: 200px; border: 2px solid #ddd;">
                        </div>
                        <div class="table-info">Code: ${qrData.code}</div>
                        <div class="table-url">${qrData.url}</div>
                        <button class="print-btn" onclick="printSingle(${qrData.table_number}, '${qrUrl}')">🖨️ Print</button>
                    </div>
                `;
            });
            
            windowContent += `
                        </div>
                        <script>
                            function printSingle(tableNumber, qrUrl) {
                                const printWindow = window.open('', '_blank');
                                printWindow.document.write(\`
                                    <html>
                                        <head>
                                            <title>Table \${tableNumber} QR Code</title>
                                            <style>
                                                body { text-align: center; font-family: Arial, sans-serif; margin: 50px; }
                                                h1 { margin-bottom: 30px; }
                                                img { border: 2px solid #ddd; }
                                                p { margin-top: 20px; font-size: 14px; color: #666; }
                                            </style>
                                        </head>
                                        <body>
                                            <h1>Table \${tableNumber}</h1>
                                            <img src="\${qrUrl}" alt="QR Code" style="width: 300px; height: 300px;">
                                            <p>Scan to view menu and place orders</p>
                                        </body>
                                    </html>
                                \`);
                                printWindow.document.close();
                                printWindow.print();
                            }
                        </script>
                    </body>
                </html>
            `;
            
            qrWindow.document.write(windowContent);
            qrWindow.document.close();
        })
        .catch(error => {
            qrWindow.document.write('<h1>Error loading QR codes</h1>');
            qrWindow.document.close();
        });
}

function printAllQRCodes() {
    openQRCodesWindow();
}