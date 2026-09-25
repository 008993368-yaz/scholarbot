# ScholarBot

Conversational academic research assistant for the CSUSB library. Students search library resources in natural language via Streamlit; LangGraph manages multi-turn memory; a typed tool searches the CSUSB Primo API.

## Stack

- **UI:** Streamlit
- **Workflow / memory:** LangGraph + `MemorySaver` (thread ID)
- **Chat LLM:** OpenRouter free model (default `nex-agi/nex-n2.5-pro:free`, with fallbacks)
- **Routing decisions:** OpenRouter Decisions API + `~typesafe/jev-latest` (search vs clarify vs chitchat)
- **Library:** CSUSB Primo public Explore REST client

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `OPENROUTER_API_KEY` from [OpenRouter keys](https://openrouter.ai/settings/keys).

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

### Docker

Ensure `.env` has `OPENROUTER_API_KEY`, then:

```bash
docker compose up --build
```

App: http://localhost:8501

## Example conversation

1. "Find recent articles about machine learning" → search + results  
2. "Show only books from 2023" → same thread reuses the topic with new filters  
3. "Find dissertations by John Smith" → clarifying question for a topic
