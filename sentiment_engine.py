# sentiment_engine.py - FINAL DEFINITIVE VERSION (Groq Compatible)

import pandas as pd
import logging
import news_handler
import llm_handler # Our new Groq-powered handler

logger = logging.getLogger(__name__)

def get_nifty50_sentiment_score():
    """
    Calculates a WEIGHTED sentiment score for the NIFTY 50 by analyzing
    the news of its top constituents using the Groq-powered Cognito persona.
    """
    try:
        weights_df = pd.read_csv("nifty50_weights.csv")
    except FileNotFoundError:
        logger.critical("FATAL: nifty50_weights.csv not found.")
        return 0.0

    total_weighted_score = 0.0
    
    logger.info("[Sentiment Engine] Analyzing news for top NIFTY 50 constituents...")
    for index, row in weights_df.iterrows():
        symbol = row['Symbol']
        weight = row['Weightage']
        
        headlines = news_handler.get_latest_headlines(symbol, count=3)
        
        headlines_str = " | ".join(headlines) if headlines else "No specific news found."
            
        logger.info(f"  -> Analyzing sentiment for {symbol} (Weight: {weight:.2f}%)...")
        tech_str = f"Current news analysis for {symbol}."
        
        # Use the new, advanced get_market_analysis function
        analysis = llm_handler.get_market_analysis(tech_str, headlines_str)
        
        if analysis:
            outlook = analysis.get('outlook', 'Neutral')
            confidence = analysis.get('confidence', 0.5)
            
            # Convert the outlook to our numerical score
            score = 0
            if "Bullish" in outlook: score = 1
            elif "Bearish" in outlook: score = -1
            
            weighted_score = score * confidence * (weight / 100.0)
            total_weighted_score += weighted_score
            
            logger.info(f"  -> {symbol} Sentiment: {outlook} | Weighted Score Contribution: {weighted_score:.4f}")

    logger.info(f"--- TOTAL NIFTY 50 WEIGHTED SENTIMENT SCORE: {total_weighted_score:.4f} ---")
    return total_weighted_score