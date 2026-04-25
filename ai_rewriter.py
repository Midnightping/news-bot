import google.generativeai as genai
import config
import logging
import random
import os

logger = logging.getLogger(__name__)

# Set up Gemini
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    logger.warning("GEMINI_API_KEY not found. AI rewriting will fail.")
    model = None

SYSTEM_PROMPT = """
You are the Lead Social Media Editor for a premium, high-end Ghana news outlet on X (Twitter). 

Your mission: Transform raw news data into authoritative, punchy, and highly engaging X posts that look and feel like top-tier journalism.

Rules for High-Quality Output:
- **Tone**: Sophisticated, well-informed, and slightly conversational. Avoid being generic or "bot-like."
- **Structure**: Lead with the most shocking or important fact. Use short, high-impact sentences.
- **Engagement**: Use one relevant, high-value emoji per post (e.g., 🇬🇭, 📈, 🚨, 🏛️).
- **Conciseness**: Keep it strictly under 260 characters to ensure perfect readability.
- **Accuracy**: Never embellish facts, but present them with maximum impact.
- **Formatting**: Use clean spacing. No "AI-isms" like "In a surprising turn of events" or "A significant development."

Original News Content:
{original_text}

Premium Rewrite for X:
"""

def rewrite_caption(original_text):
    if not model:
        logger.error("AI model not initialized.")
        return original_text
    
    try:
        # Check if there are custom prompt variants in the prompts folder
        prompt = SYSTEM_PROMPT
        if os.path.exists(config.PROMPTS_DIR):
            variants = [f for f in os.listdir(config.PROMPTS_DIR) if f.endswith('.txt')]
            if variants:
                selected_v = random.choice(variants)
                with open(os.path.join(config.PROMPTS_DIR, selected_v), 'r', encoding='utf-8') as f:
                    prompt = f.read()

        full_prompt = prompt.format(original_text=original_text)
        
        response = model.generate_content(full_prompt)
        rewritten = response.text.strip()
        
        # Clean up any quotes AI might add
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
            
        return rewritten
    except Exception as e:
        logger.error(f"Error rewriting caption: {e}")
        return original_text # Fallback to original
