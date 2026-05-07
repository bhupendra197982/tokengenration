from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, AsyncGenerator
from kotak_client import kotak_manager
from contextlib import asynccontextmanager
import asyncio
import uvicorn

# Lifespan context manager (replaces @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan events:
    - Startup: Login to Kotak Neo
    - Shutdown: Cleanup (optional)
    """
    # Startup
    print("🚀 Starting Kotak Neo Trading Server...")
    await asyncio.to_thread(kotak_manager.login)
    
    yield  # Application runs here
    
    # Shutdown (optional cleanup)
    print("🛑 Shutting down Kotak Neo Trading Server...")
    # Add any cleanup code here if needed

# Create FastAPI app with lifespan
app = FastAPI(
    title="Kotak Neo Trading Panel",
    lifespan=lifespan  # Attach lifespan handler
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class SymbolSearch(BaseModel):
    query: str

class OrderRequest(BaseModel):
    token: str
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    order_type: str  # MARKET, LIMIT, SL, SL-M
    product_type: str  # INTRADAY or NORMAL
    price: Optional[float] = 0
    trigger_price: Optional[float] = 0
    exchnange: Optional[str] = ""

class SymbolResponse(BaseModel):
    token: str
    symbol: str
    name: str
    exchange: str

@app.get("/")
async def root():
    return {
        "status": "Kotak Neo Trading Panel API",
        "logged_in": kotak_manager.is_logged_in
    }

@app.get("/api/symbols/search")
async def search_symbols(q: str = ""):
    """Search symbols with autocomplete"""
    if not q or len(q) < 2:
        return []
    
    results = await asyncio.to_thread(kotak_manager.search_symbols, q)
    
    # Format response
    formatted = []
    for item in results:
        formatted.append({
            "token": item.get("pSymbol", ""),
            "symbol": item.get("pTrdSymbol", ""),
            "name": item.get("pSymbolName", ""),
            "exchange": item.get("pExchSeg", "")
        })
    
    return formatted

@app.post("/api/order/place")
async def place_order(order: OrderRequest):
    """Place buy/sell order"""
    try:
        result = await asyncio.to_thread(kotak_manager.place_order, order.model_dump())
        return {
            "success": True,
            "message": "Order placed successfully",
            "order_id": result.get("order_id"),
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Check login status"""
    return {
        "logged_in": kotak_manager.is_logged_in,
        "status": "healthy" if kotak_manager.is_logged_in else "not_logged_in"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)