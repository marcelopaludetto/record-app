"""
Sumarização de transcrições via Claude (Anthropic API).
"""
import json
import anthropic as _anthropic
from json_repair import repair_json

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from core.prompts import PROFILES, USER_TEMPLATE


class Summarizer:
    def __init__(self):
        pass

    @property
    def backend(self) -> str:
        return "claude"

    def summarize(self, transcript: str, profile: str = "trabalho") -> dict:
        return self._summarize_claude(transcript[:150000], profile)

    def is_available(self) -> bool:
        return bool(ANTHROPIC_API_KEY.strip())

    def _summarize_claude(self, transcript: str, profile: str) -> dict:
        system_prompt = PROFILES.get(profile, PROFILES["trabalho"])
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": USER_TEMPLATE.format(transcript=transcript)}
            ],
        )
        raw = message.content[0].text
        return self._parse(raw)

    def _parse(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()

        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = json.loads(repair_json(text))
            except Exception:
                return {
                    "tipo_agenda": "",
                    "temas":       [],
                    "topics": [{"title": "Conteúdo da Reunião",
                                "bullets": [{"text": raw.strip(), "sub_bullets": []}]}],
                    "next_steps": [],
                }

        tldr = parsed.get("tldr", [])
        if isinstance(tldr, str):
            tldr = [tldr] if tldr else []

        return {
            "tipo_agenda": parsed.get("tipo_agenda", ""),
            "temas":       parsed.get("temas", []),
            "tldr":        tldr,
            "topics":      parsed.get("topics", []),
            "next_steps":  parsed.get("next_steps", []),
            "entities":    parsed.get("entities", []),
        }
