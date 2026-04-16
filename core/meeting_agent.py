"""
Agente conversacional que responde perguntas sobre reuniões e tarefas.
"""
import anthropic as _anthropic
from datetime import datetime

from config import ANTHROPIC_API_KEY
from storage.models import Meeting


SYSTEM_PROMPT = """\
Você é um assistente pessoal com acesso ao histórico de reuniões do usuário.

REGRAS:
- Responda sempre em português brasileiro
- Seja direto e acionável
- Use apenas informações presentes nos dados fornecidos — nunca invente tarefas, decisões ou participantes
- Se não houver dados suficientes, diga isso claramente
- Use listas quando listar tarefas ou informações de múltiplas reuniões
- Os dados em "DADOS DAS REUNIÕES" são atualizados a cada pergunta — sempre use esses dados para datas e fatos, nunca confie em respostas anteriores da conversa
"""


def _serialize_meetings(meetings: list[Meeting]) -> str:
    """Serializa reuniões em texto estruturado para o contexto do agente."""
    done = [m for m in meetings if m.status == "done"][:40]
    if not done:
        return "Nenhuma reunião processada encontrada."

    lines = [f"TOTAL DE REUNIÕES: {len(done)} — você DEVE processar todas as {len(done)} antes de responder.\n"]
    for i, m in enumerate(done, 1):
        date_str = m.started_at.strftime("%d/%m/%Y") if m.started_at else "?"
        lines.append(f"---")
        lines.append(f"[{i}/{len(done)}] Reunião: {m.title}")
        lines.append(f"Data: {date_str}")
        if m.tipo_agenda:
            lines.append(f"Tipo: {m.tipo_agenda}")
        if m.temas:
            lines.append(f"Temas: {', '.join(m.temas)}")
        if m.topics:
            lines.append("Tópicos discutidos:")
            for t in m.topics:
                lines.append(f"  • {t.title}")
                for b in t.bullets[:3]:
                    lines.append(f"    - {b.text}")
        if m.next_steps:
            lines.append("Próximos passos:")
            for ns in m.next_steps:
                lines.append(f"  → {ns.action}")
        lines.append("")

    return "\n".join(lines)


class MeetingAgent:
    def __init__(self):
        self._client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)
        self._history: list[dict] = []

    def ask(self, user_message: str, meetings: list[Meeting]) -> str:
        """Envia mensagem ao agente com contexto de reuniões e retorna resposta."""
        today = datetime.now().strftime("%d/%m/%Y")
        context = _serialize_meetings(meetings)
        system = SYSTEM_PROMPT + f"\n\n## DATA DE HOJE\n{today}\n\n## DADOS DAS REUNIÕES (atualizados agora)\n\n{context}"

        self._history.append({"role": "user", "content": user_message})

        response = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=system,
            messages=self._history,
        )

        reply = response.content[0].text
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def clear_history(self):
        self._history = []
