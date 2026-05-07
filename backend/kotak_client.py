import os
from neo_api_client import NeoAPI
from dotenv import load_dotenv
import pyotp
load_dotenv()
import pandas as pd
from datetime import datetime


class KotakNeoManager:
    def __init__(self):
        self.client = None
        self.session = None
        self.is_logged_in = False
        
    def login(self):
        """Auto-login on startup using environment variables. Disables SSL verification for login step (workaround for CERTIFICATE_VERIFY_FAILED)."""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        try:
            consumer_key = os.getenv("COSNSUMER_KEY")
            totp_token = os.getenv("TOTP_TOKEN")
            mobile = os.getenv("MOBILE")
            mpin = os.getenv("MPIN")
            ucc = os.getenv("UCC")

            # Patch requests to disable SSL verification for all requests (temporary workaround)
            old_request = requests.Session.request
            def unsafe_request(self, *args, **kwargs):
                kwargs['verify'] = False
                return old_request(self, *args, **kwargs)
            requests.Session.request = unsafe_request

            self.client = NeoAPI(environment='prod', access_token=None, neo_fin_key=None, consumer_key=consumer_key)
            self.client.totp_login(mobile_number=mobile, ucc=ucc, totp=pyotp.TOTP(totp_token).now())
            self.client.totp_validate(mpin=mpin)
            self.is_logged_in = True
            self.symdf = None
            print(f"✅ Kotak Neo Login Successful ")
            print('Holding',self.client.holdings())
            print("📊 Initializing Symbols...")
            self.initilaizeSymbols()
            # Restore requests after login
            requests.Session.request = old_request
            return True
        except Exception as e:
            print(f"❌ Login Failed: {e}")
            self.is_logged_in = False
            # Restore requests if error
            try:
                requests.Session.request = old_request
            except Exception:
                pass
            return False
    

    def initilaizeSymbols(self):
        dateFormat = datetime.now().strftime("%Y-%m-%d")
        cmdf = pd.read_csv(f'https://lapi.kotaksecurities.com/wso2-scripmaster/v1/prod/{dateFormat}/transformed-v1/nse_cm-v1.csv')
        self.symdf = cmdf[cmdf.pGroup.isin(['EQ','BE','BL'])]
        print(f"✅ Symbols Initialized {self.symdf.shape[0]} symbols loaded \n {self.symdf}")



    def search_symbols(self, query: str):
        """Search trading symbols"""
        if not self.is_logged_in:
            return []
        
        try:
            # Get search results from Kotak API
            results = self.symdf[self.symdf['pTrdSymbol'].str.contains(query, case=False, na=False)].to_dict(orient='records')
            return results if results else []
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def place_order(self, order_data: dict):
        """Place order to Kotak Neo"""
        if not self.is_logged_in:
            raise Exception("Not logged in")
        
        try:
            # Map frontend order types to Kotak API format
            print(f"Placing order with data: {order_data}")
            order_type_map = {
                "MARKET": "MKT",
                "LIMIT": "L",
                "SL": "SL",
                "SL-M": "SL-M"
            }
            
            product_map = {
                "INTRADAY": "MIS",
                "NORMAL": "NRML"
            }
            
            side_map = {
                "BUY": "B",
                "SELL": "S"
            }
            

            response =self.client.place_order(
                exchange_segment=order_data.get('exchnange', 'nse_cm'),
                product=product_map[order_data['product_type']],
                price=str(order_data.get('price', 0)),
                order_type=order_type_map[order_data['order_type']],
                quantity=str(order_data['quantity']),
                validity="DAY",
                trading_symbol=order_data['symbol'],
                transaction_type=side_map[order_data['side']],
                amo="NO",
                disclosed_quantity="0",
                market_protection="0",
                pf="N",
                trigger_price=str(order_data.get('trigger_price', 0)),
            
            )
            print(f"Order Response: {response}")
            return response
            
        except Exception as e:
            raise Exception(f"Order placement failed: {str(e)}")

# Global client instance
kotak_manager = KotakNeoManager()