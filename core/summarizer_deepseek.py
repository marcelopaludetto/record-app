"""
Sumarização de transcrições via DeepSeek API.
"""
import time

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL
from core.prompts import PROFILES, USER_TEMPLATE
from core.summarizer import Summarizer as _BaseSummarizer

DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_CHAT_URL = f"{DEEPSEEK_BASE}/chat/completions"
DEEPSEEK_MODELS_URL = f"{DEEPSEEK_BASE}/models"


class DeepSeekSummarizer(_BaseSummarizer):

    @property
    def backend(self) -> str:
        return "deepseek"

    @property
    def model(self) -> str:
        return DEEPSEEK_MODEL

    def is_available(self) -> bool:
        return bool(DEEPSEEK_API_KEY.strip())

    def ping(self) -> tuple[bool, str]:
        """Verifica conectividade real com a API DeepSeek. Retorna (ok, mensagem)."""
        if not DEEPSEEK_API_KEY.strip():
            return False, "Chave API ausente"
        try:
            r = httpx.get(
                DEEPSEEK_MODELS_URL,
                headers=_headers(),
                timeout=8.0,
            )
            if r.status_code == 200:
                return True, ""
            if r.status_code == 401:
                return False, "Chave API inválida"
            if r.status_code == 403:
                return False, "Acesso negado (403)"
            if r.status_code == 429:
                return False, "Rate limit atingido (429)"
            if r.status_code >= 500:
                return False, f"Serviço indisponível ({r.status_code})"
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
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": False,
            "response_format": {"type": "json_object"},
            # Resumo estruturado não precisa de modo de raciocínio; desabilitar reduz custo e latência.
            "thinking": {"type": "disabled"},
        }

        retries = 3
        delay = 5
        response = None
        for attempt in range(retries):
            response = httpx.post(
                DEEPSEEK_CHAT_URL,
                headers=_headers(),
                json=payload,
                timeout=180.0,
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            break

        data = response.json()
        text = data["choices"][0]["message"].get("content") or ""
        return self._parse(text)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
