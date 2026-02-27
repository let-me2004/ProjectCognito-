# llm_handler.py - FINAL DEFINITIVE VERSION (Groq High-Speed)

from groq import Groq
import config
import logging
import json
import time

logger = logging.getLogger(__name__)

# --- Groq Client Initialization ---
try:
    if not config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in .env file.")
    
    client = Groq(api_key=config.GROQ_API_KEY)
    
    # Using a current, stable, and fast model from Groq
    MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct" 

    logger.info(f"Groq client initialized successfully for model: {MODEL_NAME}")

except Exception as e:
    logger.critical(f"Failed to initialize Groq client: {e}", exc_info=True)
    client = None
# --------------------------------

def get_market_analysis(technical_data, news_headlines):
    """
    Takes market data, gets analysis from the Groq-powered 'Cognito' persona,
    and sanitizes the output.
    """
    if client is None:
        logger.error("Groq client not initialized. Cannot get analysis.")
        return None

    if not news_headlines:
        news_headlines = "No specific news found."

    prompt = f"""
    **Persona:**
    You are 'Cognito', a senior quantitative sentiment analyst for the Indian stock market. Your sole purpose is to analyze real-time data to provide a decisive, short-term directional bias. You are data-driven and precise. Only use "Neutral" when data is perfectly contradictory.

    **Rules of Analysis:**
    1.  **Negative Bias:** Give slightly more weight to negative news.
    2.  **Output Format:** You MUST return your analysis ONLY as a single, clean JSON object with the keys "outlook" (String: "Bullish", "Bearish", or "Neutral") and "confidence" (Float: 0.0 to 1.0).

    ---
    **Live Data for Analysis:**

    * **Technical Snapshot:** "{technical_data}"
    * **Key News Headlines:** "{news_headlines}"

    Provide your JSON output now.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model=MODEL_NAME,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        
        response_content = chat_completion.choices[0].message.content
        analysis_dict = json.loads(response_content)

        # --- Data Sanitization Protocol ---
        if 'confidence' in analysis_dict:
            try:
                analysis_dict['confidence'] = float(analysis_dict['confidence'])
            except (ValueError, TypeError):
                logger.warning(f"Groq returned invalid confidence value. Defaulting to 0.0.")
                analysis_dict['confidence'] = 0.0
        else:
            logger.warning("Groq response was missing 'confidence' key. Defaulting to 0.0.")
            analysis_dict['confidence'] = 0.0

        return analysis_dict

    except Exception as e:
        logger.error(f"Error getting or parsing analysis from Groq: {e}", exc_info=True)
        return None

# --- Standalone Test Block ---
if __name__ == '__main__':
    # --- THIS IS THE FIX ---
    import logger_setup 
    # --------------------
    logger_setup.setup_logger()
    logger.info("--- Standalone Groq Handler Test ---")
    
    if not config.GROQ_API_KEY:
        logger.critical("Cannot run test: GROQ_API_KEY not set in .env file.")
    else:
        test_techs = "NIFTY at 25100. RSI is 68. Above all key EMAs."
        test_news = "Major IT firm reports stellar earnings, raises guidance for the year."
        
        logger.info("Testing with positive data...")
        analysis = get_market_analysis(test_techs, test_news)
        
        if analysis:
            logger.info(f"--> Result: {json.dumps(analysis, indent=2)}")
        else:
            logger.error("--> Failed to get analysis.")

