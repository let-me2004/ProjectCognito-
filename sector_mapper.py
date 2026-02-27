import pandas as pd
import logging

logger = logging.getLogger(__name__)

# --- CORRECTED FYERS SECTOR SYMBOLS ---
SECTOR_SYMBOL_MAP = {
    "Nifty Auto": "NSE:NIFTYAUTO-INDEX",
    "Automobile and Auto Components": "NSE:NIFTYAUTO-INDEX",
    
    "Nifty Bank": "NSE:NIFTYBANK-INDEX",
    
    "Nifty Consumer Durables": "NSE:NIFTY_CONSUMER_DURABLES-INDEX",
    "Consumer Durables": "NSE:NIFTY_CONSUMER_DURABLES-INDEX",
    
    "Nifty Financial Services": "NSE:FINNIFTY-INDEX",
    "Financial Services": "NSE:FINNIFTY-INDEX",
    
    "Nifty FMCG": "NSE:NIFTYFMCG-INDEX",
    "Fast Moving Consumer Goods": "NSE:NIFTYFMCG-INDEX",
    
    "Nifty IT": "NSE:NIFTYIT-INDEX",
    "Information Technology": "NSE:NIFTYIT-INDEX",
    
    "Nifty Media": "NSE:NIFTYMEDIA-INDEX",
    "Media Entertainment & Publication": "NSE:NIFTYMEDIA-INDEX",
    
    "Nifty Metal": "NSE:NIFTYMETAL-INDEX",
    "Metals & Mining": "NSE:NIFTYMETAL-INDEX",
    
    "Nifty Pharma": "NSE:NIFTYPHARMA-INDEX",
    "Healthcare": "NSE:NIFTYPHARMA-INDEX",
    
    "Nifty PSU Bank": "NSE:NIFTYPSUBANK-INDEX",
    
    "Nifty Private Bank": "NSE:NIFTYPVTBANK-INDEX",
    
    "Nifty Realty": "NSE:NIFTYREALTY-INDEX",
    "Realty": "NSE:NIFTYREALTY-INDEX",
    "Construction": "NSE:NIFTYREALTY-INDEX", # Closest proxy
    
    "Nifty Oil & Gas": "NSE:NIFTY_OIL_AND_GAS-INDEX",
    "Oil Gas & Consumable Fuels": "NSE:NIFTY_OIL_AND_GAS-INDEX",
    
    "Power": "NSE:NIFTYENERGY-INDEX", # Mapping Power to Energy Index
    "Capital Goods": "NSE:NIFTYINFRA-INDEX", # Mapping Cap Goods to Infra as proxy or closest available
    "Chemicals": "NSE:NIFTYCOMMODITIES-INDEX", # Proxy
    "Services": "NSE:NIFTYSERVSECTOR-INDEX",
    # Add other mappings as needed
}

class SectorMapper:
    def __init__(self, filepath="nifty200_symbols.csv"):
        self.mapping = self._create_mapping(filepath)
        if self.mapping:
            logger.info("Successfully created stock-to-sector mapping for NIFTY 200.")

    def _create_mapping(self, filepath):
        try:
            df = pd.read_csv(filepath)
            # Create a dictionary mapping stock symbol to its sector
            # This logic handles variations like INFY vs INFY.NS
            mapping = {
                f"NSE:{row['Symbol']}-EQ": row['Industry'] 
                for index, row in df.iterrows()
            }
            return mapping
        except FileNotFoundError:
            logger.critical(f"FATAL: Sector mapping file not found at {filepath}")
            return None
        except Exception as e:
            logger.error(f"Error creating sector mapping: {e}", exc_info=True)
            return None

    def get_sector_for_stock(self, stock_symbol):
        """
        Gets the sector name for a given stock symbol (e.g., 'NSE:INFY-EQ').
        """
        if self.mapping is None: return None
        return self.mapping.get(stock_symbol)

    def get_fyers_sector_symbol(self, sector_name):
        """
        Gets the correct Fyers API symbol for a given sector name.
        """
        if sector_name is None: return None
        return SECTOR_SYMBOL_MAP.get(sector_name)
