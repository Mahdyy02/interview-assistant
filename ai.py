import httpx
from dotenv import load_dotenv
import os

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def generate_chatbot_response(system_prompt: str,
            user_message: str,
            temperature: float,
            max_tokens: int,
            context: str = "") -> str:

    try:
        headers = {
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        }
        
        # Build the user message with RAG context if provided
        full_user_message = user_message
        if context:
            full_user_message = f"{context}\n\n### INTERVIEW QUESTION:\n{user_message}"
        
        payload = {
            "model": "mistralai/mistral-small-3.1-24b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_user_message}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']

    except Exception as e:
        print(f"LLM general conversation error: {e}")

