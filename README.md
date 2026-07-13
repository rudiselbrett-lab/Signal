# Forge

**Forge helps professionals turn information into lasting expertise.**

Not another read-it-later app: Forge continuously discovers high-value content, helps you understand it, reinforces it over time with spaced repetition, and lets you apply everything you've learned through an AI coach grounded exclusively in your own knowledge library.

```
Suggest → Learn → Reinforce → Apply (AI Q&A) → Improve future suggestions
   ▲                                                      │
   └──────────────────────────────────────────────────────┘
```

## Status

🏗️ **Architecture review** — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete proposed system design. Implementation begins after the architecture is approved, one feature per phase (roadmap in §15 of that document).

## Planned stack

- **Frontend:** Next.js · TypeScript · Tailwind · shadcn/ui
- **Backend:** Python · FastAPI · domain-driven modular monolith
- **Data:** PostgreSQL + pgvector (hybrid semantic + keyword search)
- **Jobs:** Celery + Redis
- **AI:** Anthropic Claude (understanding, reinforcement, coach) · OpenAI `text-embedding-3-large` (embeddings)
