"""
Sumarização de transcrições via Claude (Anthropic API).
"""
import json
import anthropic as _anthropic
from json_repair import repair_json

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Você é uma IA especialista em transformar transcrições de reuniões em notas estruturadas.
Seu modelo de referência é o Granola.ai: notas limpas, hierárquicas e sem seções artificiais.

ESTILO DE SAÍDA:
- Agrupe o conteúdo em tópicos temáticos com títulos curtos e descritivos
- Use bullets simples e concisos: uma ideia por linha, sem floreios
- Sub-bullets são permitidos apenas quando um ponto precisa de desdobramento direto (ex: argumentos de uma decisão, condições de uma proposta). Máximo 1 nível.
- Decisões, riscos, próximas ações e contexto devem ser embutidos NATURALMENTE como bullets dentro do tópico onde ocorreram — não crie seções separadas para eles
- Títulos de tópico no formato "Assunto - Contexto" quando útil (ex: "Duplicação de Unidades - 2º Bimestre")

REGRAS DE CONTEÚDO:
- Nunca use aspas duplas dentro dos valores de texto — use aspas simples ou paráfrase
- Evite informações redundantes — se um ponto já apareceu num tópico, não repita em outro tópico nem nos next_steps
- Nunca invente nomes, datas, decisões ou responsabilidades
- Só inclua o que há evidência clara na transcrição
- Não transforme opiniões em decisões
- Não crie responsáveis se não foram mencionados explicitamente
- Não infira prazos — só inclua se dito na reunião
- Escreva em português brasileiro

TLDR:
- 2 a 4 frases curtas (máx. 15 palavras cada) que resumem o essencial da reunião
- Deve ser compreensível por alguém que não participou
- Foque em decisões e encaminhamentos, não em processo

REGRAS DE MENÇÃO A PARTICIPANTES:
- Mencione nomes próprios APENAS quando a autoria é essencial para entender o ponto (ex: quem propôs algo controverso, quem vetou, quem ficou responsável)
- Para aprovações, validações e concordâncias genéricas, use voz passiva ou impessoal: 'Aprovado', 'Validado', 'Acordado' — não 'Fulano aprovou'
- Se o mesmo participante é mencionado em 3+ bullets consecutivos, reescreva para reduzir: o leitor já sabe quem está falando pelo contexto do tópico
- Preferências pessoais só devem ser atribuídas por nome quando impactam uma decisão concreta

ORGANIZAÇÃO DE BULLETS:
- Cada bullet deve ser auto-contido: quem lê isolado entende o ponto
- Máximo 12 palavras por bullet — corte o que for contexto óbvio ou repetição
- Agrupe bullets por sub-tema dentro do tópico. Sequência lógica: contexto → discussão → decisão/encaminhamento
- Separe claramente fatos (o que foi dito/mostrado) de decisões (o que foi acordado)
- Cada bullet deve ser compreensível sem depender do bullet anterior — evite pronomes sem referente claro ("ele decidiu", "isso foi aprovado")

CLASSIFICAÇÃO (para metadados):
- tipo_agenda (escolha 1): 1on1 | com cliente | followup | time todo
- temas (2 a 5 tags curtas em português, minúsculas, descrevendo os assuntos principais da reunião. palavras compostas precisam ter hífen, ex: "duplicação-unidades", "educação-midiática")

ENTIDADES (para wikilinks no Obsidian):
- Retorne um campo "entities": lista de pessoas e projetos mencionados explicitamente nas notas
- Inclua apenas entidades que aparecem no conteúdo dos bullets, next_steps ou tldr
- type "person" para pessoas, "project" para projetos/iniciativas/produtos/ferramentas
- Use o nome canônico mais curto (ex: "Alana", não "Alana Silva"; "SEED-PR", não "projeto SEED-PR")
- Se não houver entidades relevantes, retorne lista vazia

NEXT_STEPS:
- Liste APENAS o que ficou pendente, não alinhado, ou precisa ser validado/refinado após a reunião
- Não repita nada que já apareceu como bullet em qualquer tópico acima
- Se um próximo passo já foi mencionado num tópico, ele NÃO entra aqui — os next_steps são para o que não coube naturalmente em nenhum tópico
- Não atribua responsável
- Se não há pendências reais, retorne lista vazia
"""

USER_TEMPLATE = """\
Analise a transcrição e responda SOMENTE com JSON válido, sem texto antes ou depois:

{{
  "tipo_agenda": "followup",
  "temas": ["planejamento", "produto", "cliente"],
  "tldr": ["frase curta resumindo decisão principal", "outro ponto essencial se necessário"],
  "topics": [
    {{
      "title": "Título Curto do Tópico",
      "bullets": [
        {{"text": "ponto central claro e conciso", "sub_bullets": []}},
        {{"text": "outro ponto importante", "sub_bullets": ["desdobramento direto se necessário"]}}
      ]
    }}
  ],
  "next_steps": [
    {{"action": "o que precisa ser validado ou refinado"}}
  ],
  "entities": [
    {{"name": "Alana", "type": "person"}},
    {{"name": "SEED-PR", "type": "project"}}
  ]
}}

TRANSCRIÇÃO:
{transcript}
"""


class Summarizer:
    def __init__(self):
        pass

    @property
    def backend(self) -> str:
        return "claude"

    def summarize(self, transcript: str) -> dict:
        return self._summarize_claude(transcript[:150000])

    def is_available(self) -> bool:
        return bool(ANTHROPIC_API_KEY.strip())

    def _summarize_claude(self, transcript: str) -> dict:
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
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
        return {
            "tipo_agenda": parsed.get("tipo_agenda", ""),
            "temas":       parsed.get("temas", []),
            "tldr":        parsed.get("tldr", []),
            "topics":      parsed.get("topics", []),
            "next_steps":  parsed.get("next_steps", []),
            "entities":    parsed.get("entities", []),
        }
