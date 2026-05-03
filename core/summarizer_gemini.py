"""
Sumarização de transcrições via Google Gemini API.
"""
import json
import time
import httpx

from config import GEMINI_API_KEY
from core.prompts import PROFILES, USER_TEMPLATE
from core.summarizer import Summarizer as _BaseSummarizer

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_URL = (
    f"{GEMINI_BASE}/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
GEMINI_PING_URL = f"{GEMINI_BASE}/models?key={GEMINI_API_KEY}&pageSize=1"


class GeminiSummarizer(_BaseSummarizer):

    @property
    def backend(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return GEMINI_MODEL

    def is_available(self) -> bool:
        return bool(GEMINI_API_KEY.strip())

    def ping(self) -> tuple[bool, str]:
        """Verifica conectividade real com a API Gemini. Retorna (ok, mensagem)."""
        if not GEMINI_API_KEY.strip():
            return False, "Chave API ausente"
        try:
            r = httpx.get(GEMINI_PING_URL, timeout=8.0)
            if r.status_code == 200:
                return True, ""
            if r.status_code == 400:
                return False, "Chave API inválida"
            if r.status_code == 403:
                return False, "Acesso negado (403)"
            if r.status_code == 429:
                return False, "Rate limit atingido (429)"
            if r.status_code == 503:
                return False, "Serviço indisponível (503)"
            return False, f"Erro HTTP {r.status_code}"
        except httpx.TimeoutException:
            return False, "Timeout ao conectar"
        except httpx.ConnectError:
            return False, "Sem conexão com a API"
        except Exception as e:
            return False, str(e)

    def summarize(self, transcript: str, profile: str = "trabalho") -> dict:
        system_prompt = PROFILES.get(profile, PROFILES["trabalho"])
        prompt = USER_TEMPLATE.format(transcript=transcript[:800000])
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        }
        retries = 3
        delay = 10
        for attempt in range(retries):
            response = httpx.post(GEMINI_URL, json=payload, timeout=180.0)
            if response.status_code == 503 and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            break
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse(text)
