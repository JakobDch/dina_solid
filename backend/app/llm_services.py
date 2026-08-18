import requests
import asyncio
from openai import OpenAI as OpenAIClient
import logging
from pydantic import BaseModel, Field
import json
from typing import Optional
logger = logging.getLogger(__name__)

class OpenAILLM:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        if not api_key:
            raise ValueError("OpenAI API Key wurde nicht an den Konstruktor übergeben.")
        self.client = OpenAIClient(api_key=api_key, base_url=base_url, timeout=60.0)  # 60 second timeout
        self.model = model

    def invoke(self, prompt_text: str, system_message: str = "Du bist ein hilfsbereiter Assistent.", temperature: float = 0.0):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt_text}
                ],
                stream=False,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API Fehler: {type(e).__name__} - {str(e)[:100]}")
            return f"Fehler: bei der Anfrage an OpenAI ({self.model}): {type(e).__name__}"



class OllamaLLM:
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

    def invoke(self, prompt_text: str, system_message: str = "Du bist ein hilfsbereiter Assistent.", temperature: float = 0.0):
        timeout_seconds = 120
        try:
            api_endpoint = self.base_url
            if not api_endpoint.endswith('/v1/chat/completions'):
                if api_endpoint.endswith('/'):
                    api_endpoint += 'v1/chat/completions'
                else:
                    api_endpoint += '/v1/chat/completions'
            
            headers = {"Content-Type": "application/json"}
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt_text}
                ],
                "stream": False,
                "temperature": temperature,
                "options": { 
                    "num_ctx": 4096 
                }
            }

            def sync_post():
                return requests.post(api_endpoint, headers=headers, json=data, timeout=timeout_seconds)

            # Asyncio-freundlich: Wenn ein Eventloop läuft, führe sync_post im Threadpool aus
            try:
                loop = asyncio.get_running_loop()
                # Wenn wir im Eventloop sind, mache den Netzwerkcall asynchron
                response = loop.run_until_complete(loop.run_in_executor(None, sync_post)) if loop.is_running() else sync_post()
            except RuntimeError:
                # Kein laufender Eventloop (klassischer Celery-Task etc.)
                response = sync_post()

            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            return f"Fehler: Timeout bei der Anfrage an Ollama ({self.model}) nach {timeout_seconds} Sekunden."
        except requests.exceptions.RequestException as e:
            return f"Fehler: bei der Anfrage an Ollama ({self.model}): {e}"
        except KeyError:
            return f"Fehler: Unerwartete Antwortstruktur von Ollama ({self.model}). Antwort: {response.text}"


class DeepSeekLLM:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.deepseek.com/v1"): # /v1 hinzugefügt
        if not api_key:
            
            raise ValueError("DeepSeek API Key wurde nicht an den Konstruktor übergeben.")
        self.client = OpenAIClient(api_key=api_key, base_url=base_url, timeout=60.0)  # 60 second timeout
        self.model = model

    def invoke(self, prompt_text: str, system_message: str = "Du bist ein hilfsbereiter Assistent.", temperature: float = 0.0):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt_text}
                ],
                stream=False,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek API error: {type(e).__name__} - {str(e)}", exc_info=True)
            print(f"DeepSeek API Fehler: {type(e).__name__} - {str(e)[:100]}") 
            return f"Fehler: bei der Anfrage an DeepSeek ({self.model}): {type(e).__name__}"


class ChatMessageRequest(BaseModel):
    message: str
    llm_profile: str = Field(default="ollama_local_gemma3", description="Identifier for the LLM configuration to use.")

     

class ChatMessageResponse(BaseModel):
    reply: str