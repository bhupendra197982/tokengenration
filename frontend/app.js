// Configuration
const API_BASE_URL = 'http://localhost:8000';
let searchTimeout = null;
let currentOrderType = 'MARKET';
let currentProductType = 'INTRADAY';

// DOM Elements
const symbolInput = document.getElementById('symbolInput');
const symbolDropdown = document.getElementById('symbolDropdown');
const symbolList = document.getElementById('symbolList');
const selectedToken = document.getElementById('selectedToken');
const selectedSymbol = document.getElementById('selectedSymbol');
const quantityInput = document.getElementById('quantityInput');
const priceInput = document.getElementById('priceInput');
const triggerPriceInput = document.getElementById('triggerPriceInput');
const priceFields = document.getElementById('priceFields');
const triggerPriceField = document.getElementById('triggerPriceField');
const buyBtn = document.getElementById('buyBtn');
const sellBtn = document.getElementById('sellBtn');
const statusMessage = document.getElementById('statusMessage');
const symbolDisplay = document.getElementById('symbolDisplay');
const displaySymbol = document.getElementById('displaySymbol');
const displayExchange = document.getElementById('displayExchange');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkHealth();
});

// Event Listeners
function setupEventListeners() {
    // Symbol Search with Debounce
    symbolInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        
        if (query.length < 2) {
            hideDropdown();
            return;
        }
        
        searchTimeout = setTimeout(() => searchSymbols(query), 300);
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.field')) {
            hideDropdown();
        }
    });

    // Order Type Selection
    document.querySelectorAll('.order-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.order-type-btn').forEach(b => {
                b.classList.remove('is-selected', 'is-info');
            });
            btn.classList.add('is-selected', 'is-info');
            currentOrderType = btn.dataset.type;
            togglePriceFields();
        });
    });

    // Product Type Selection
    document.querySelectorAll('.product-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.product-type-btn').forEach(b => {
                b.classList.remove('is-selected', 'is-warning');
            });
            btn.classList.add('is-selected', 'is-warning');
            currentProductType = btn.dataset.type;
        });
    });

    // Buy/Sell Buttons
    buyBtn.addEventListener('click', () => placeOrder('BUY'));
    sellBtn.addEventListener('click', () => placeOrder('SELL'));
}

// Search Symbols
async function searchSymbols(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/symbols/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        renderSymbolDropdown(data);
    } catch (error) {
        console.error('Search error:', error);
    }
}

// Render Dropdown
function renderSymbolDropdown(symbols) {
    if (!symbols || symbols.length === 0) {
        hideDropdown();
        return;
    }

    // Wrap in dropdown-content for proper Bulma styling
    symbolList.innerHTML = `
        <div class="dropdown-content">
            ${symbols.map(s => `
                <div class="dropdown-item" onclick="selectSymbol('${s.token}', '${s.symbol}', '${s.name}', '${s.exchange}')">
                    <div class="symbol-name">${s.symbol}</div>
                    <div class="company-name">${s.name}</div>
                    <span class="tag is-small is-light exchange-tag">${s.exchange}</span>
                </div>
            `).join('')}
        </div>
    `;

    symbolDropdown.classList.remove('is-hidden');
    symbolDropdown.classList.add('is-active');
}

function hideDropdown() {
    symbolDropdown.classList.add('is-hidden');
    symbolDropdown.classList.remove('is-active');
}

// Select Symbol
function selectSymbol(token, symbol, name, exchange) {
    selectedToken.value = token;
    selectedSymbol.value = symbol;
    symbolInput.value = `${symbol}`;
    displayExchange.value = exchange;
    
    displaySymbol.textContent = symbol;
    displayExchange.textContent = exchange;
    symbolDisplay.classList.remove('is-hidden');
    
    hideDropdown();
}



// Toggle Price Fields based on Order Type
function togglePriceFields() {
    if (currentOrderType === 'MARKET') {
        priceFields.classList.add('is-hidden');
        priceInput.value = '';
        triggerPriceInput.value = '';
    } else {
        priceFields.classList.remove('is-hidden');
        
        if (currentOrderType === 'LIMIT') {
            triggerPriceField.classList.add('is-hidden');
            triggerPriceInput.value = '';
        } else {
            triggerPriceField.classList.remove('is-hidden');
        }
    }
}

// Place Order
async function placeOrder(side) {
    // Validation
    if (!selectedToken.value) {
        showStatus('Please select a symbol', 'is-danger');
        return;
    }

    const quantity = parseInt(quantityInput.value);
    if (!quantity || quantity < 1) {
        showStatus('Please enter valid quantity', 'is-danger');
        return;
    }

    // Price validation for non-market orders
    let price = 0.0;
    let triggerPrice = 0.0;
    
    if (currentOrderType !== 'MARKET') {
       
        if (currentOrderType === 'LIMIT') {
            price = parseFloat(priceInput.value);
            if (!price || price <= 0) { 
                showStatus('Please enter valid price', 'is-danger');
                return;
            }
        }
        
        if (currentOrderType === 'SL') {
            price = parseFloat(priceInput.value);
            triggerPrice = parseFloat(triggerPriceInput.value);
            if (!triggerPrice || triggerPrice <= 0 ||  !price || price <= 0) {
                showStatus('Please enter valid trigger price', 'is-danger');
                return;
            }
        }

         if (currentOrderType === 'SL-M') {
            triggerPrice = parseFloat(triggerPriceInput.value);
            if (!triggerPrice || triggerPrice <= 0) {
                showStatus('Please enter valid trigger price', 'is-danger');
                return;
            }
        }
    }

    // Disable buttons
    setLoading(true);

    const orderData = {
        token: selectedToken.value,
        symbol: selectedSymbol.value,
        side: side,
        quantity: quantity,
        order_type: currentOrderType,
        product_type: currentProductType,
        price: price,
        trigger_price: triggerPrice,
        exchnange: displayExchange.value
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/order/place`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(orderData)
        });

        const result = await response.json();

        if (response.ok) {
            //console.log(JSON.stringify(result.data, null, 2));
            showStatus(
                `✅ ${side} Order Placed! <br> ${JSON.stringify(result.data, null, 2)}`, 
                side === 'BUY' ? 'is-success' : 'is-danger'
            );
            resetForm();
        } else {
            showStatus(`❌ Error: ${result.detail}`, 'is-danger');
        }
    } catch (error) {
        showStatus(`❌ Network Error: ${error.message}`, 'is-danger');
    } finally {
        setLoading(false);
    }
}

// UI Helpers
function showStatus(message, type) {
    statusMessage.innerHTML = message;
    statusMessage.className = `notification ${type} mt-4`;
    statusMessage.classList.remove('is-hidden');
    
    setTimeout(() => {
        statusMessage.classList.add('is-hidden');
    }, 5000);
}

function setLoading(loading) {
    buyBtn.disabled = loading;
    sellBtn.disabled = loading;
    
    if (loading) {
        buyBtn.classList.add('is-loading');
        sellBtn.classList.add('is-loading');
    } else {
        buyBtn.classList.remove('is-loading');
        sellBtn.classList.remove('is-loading');
    }
}

function resetForm() {
    symbolInput.value = '';
    selectedToken.value = '';
    selectedSymbol.value = '';
    quantityInput.value = '1';
    priceInput.value = '';
    triggerPriceInput.value = '';
    symbolDisplay.classList.add('is-hidden');
    
    // Reset to defaults
    currentOrderType = 'MARKET';
    currentProductType = 'INTRADAY';
    
    document.querySelectorAll('.order-type-btn').forEach(b => {
        b.classList.remove('is-selected', 'is-info');
        if (b.dataset.type === 'MARKET') b.classList.add('is-selected', 'is-info');
    });
    
    document.querySelectorAll('.product-type-btn').forEach(b => {
        b.classList.remove('is-selected', 'is-warning');
        if (b.dataset.type === 'INTRADAY') b.classList.add('is-selected', 'is-warning');
    });
    
    togglePriceFields();
}

// Health Check
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        const data = await response.json();
        
        if (!data.logged_in) {
            showStatus('⚠️ Not logged in to Kotak Neo', 'is-warning');
        }
    } catch (error) {
        showStatus('⚠️ Cannot connect to backend', 'is-warning');
    }
}