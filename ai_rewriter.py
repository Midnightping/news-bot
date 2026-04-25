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
You are a social media editor for a popular Ghana news account on X (Twitter). 

Your job: Rewrite the following news caption to be engaging, punchy, and native to X culture.

Rules:
- Keep it under 270 characters.
- Use a confident, slightly conversational tone.
- DO NOT use hashtags excessively (max 1-2 relevant ones).
- DO NOT start with "Breaking:" on everything.
- Use emojis sparingly and naturally (🇬🇭 is fine).
- Preserve all factual accuracy.
- Never use AI-sounding phrases like "In a significant development".
- Vary your sentence structures.

Original News Content:
{original_text}

Rewrite for X:
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
