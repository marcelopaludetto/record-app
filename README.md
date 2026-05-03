# Meeting Recorder

Grava reuniões, transcreve com Whisper e gera notas estruturadas automaticamente usando IA.

## O que faz

- Grava microfone + áudio do sistema (Teams, Meet, etc.) simultaneamente
- Transcreve via **Groq Whisper**
- Resume com **Gemini 2.5 Flash** ou **Claude Haiku** — tópicos, próximos passos, TLDR
- Exporta nota em Markdown para sua pasta (compatível com Obsidian)
- Importa áudios ou transcrições existentes
- **Assistente IA**: pergunte em linguagem natural sobre suas tarefas e reuniões

## Requisitos

- Windows 10/11
- Python 3.11 ou superior — [python.org](https://www.python.org/downloads/)
- Chaves de API (ver abaixo)

## Instalação

### 1. Clone o repositório

```
git clone <url-do-repo>
cd meeting-recorder
```

### 2. Execute o setup

Dê duplo clique em **`setup.bat`** ou rode no terminal:

```
setup.bat
```

Isso cria o ambiente virtual e instala todas as dependências automaticamente.

### 3. Configure as chaves de API

O setup cria um arquivo `.env` na pasta do projeto. Abra-o em qualquer editor e preencha:

```
GROQ_API_KEY=sua_chave_aqui
ANTHROPIC_API_KEY=sua_chave_aqui
GEMINI_API_KEY=sua_chave_aqui
DEEPSEEK_API_KEY=sua_chave_aqui
SUMMARIZER_BACKEND=deepseek
```

Onde obter cada chave:

| Chave | Onde obter | Obrigatória? |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Sim (transcrição) |
| `GEMINI_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Para usar backend Gemini |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Para usar backend Claude |
| `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com) | Para usar backend DeepSeek |

> O backend inicial é definido por `SUMMARIZER_BACKEND`: `claude`, `gemini` ou `deepseek`. A escolha feita no app fica salva em `settings.json`.

### 4. Inicie o app

Dê duplo clique em **`run.bat`**.

---

## Iniciar com o Windows (opcional)

No ícone da bandeja (canto inferior direito), clique com botão direito → **Iniciar com o Windows**.

## Pasta de notas

Por padrão, as notas são salvas em `Documentos\Notes`. Para alterar, clique em **Alterar pasta** na tela principal.
