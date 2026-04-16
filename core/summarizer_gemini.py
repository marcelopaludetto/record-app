"""
Sumarização de transcrições via Google Gemini API.
"""
import json
import time
import httpx

from config import GEMINI_API_KEY
from core.summarizer import SYSTEM_PROMPT, USER_TEMPLATE
from core.summarizer import Summarizer as _BaseSummarizer

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)


class GeminiSummarizer(_BaseSummarizer):

    @property
    def backend(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(GEMINI_API_KEY.strip())

    def summarize(self, transcript: str) -> dict:
        prompt = USER_TEMPLATE.format(transcript=transcript[:800000])
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3},
        }
        retries = 3
        delay = 10  # segundos
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
