# Privacy Policy — forgeSDLC

**Effective date:** April 2026
**Contact:** ag.chaudhari.1512@gmail.com
**Last updated:** April 2026

---

## What forgeSDLC Is

forgeSDLC is a developer productivity tool that orchestrates AI coding tools
(Cursor, Claude Code, Copilot, Windsurf) through the MCP (Model Context
Protocol) standard. It runs locally on the developer's machine.

---

## What We Store

### API Keys
API keys (OpenAI, Groq, Google, Anthropic, etc.) are stored **exclusively in
your operating system's keychain**:
- macOS: Keychain Access
- Windows: Windows Credential Manager
- Linux: Secret Service (libsecret)

**API key values are never transmitted to forgeSDLC servers.** forgeSDLC has
no central servers. The keys are read locally and sent directly to the
respective AI provider APIs.

### Pipeline Metadata
Pipeline run records (project IDs, run IDs, timestamps, HITL round counts,
cost estimates) are stored in **your own PostgreSQL database**. You control
this database — forgeSDLC connects to it via the `DATABASE_URL` you configure.

### Project Context
Project context graphs, architecture decisions, and organisational memory are
stored in **your local `./chroma_db/` directory** (ChromaDB PersistentClient).
This data never leaves your machine.

---

## What We Do NOT Store

- Source code content
- API key values (only OS keychain handles)
- Telemetry or usage analytics (without explicit opt-in)
- Personal data beyond what you explicitly provide in prompts
- Biometric data of any kind

---

## Third-Party AI Providers

When you configure forgeSDLC to use an AI provider, your prompts and code
context are sent to that provider according to **their** privacy policies:

- [OpenAI Privacy Policy](https://openai.com/privacy)
- [Groq Privacy Policy](https://groq.com/privacy-policy/)
- [Google Privacy Policy](https://policies.google.com/privacy)
- [Anthropic Privacy Policy](https://www.anthropic.com/privacy)

forgeSDLC does not control these providers. Review their policies before
enabling them.

---

## Your Rights (GDPR/CCPA)

Since all your data is stored in infrastructure you control (your PostgreSQL,
your ChromaDB, your OS keychain), you exercise your rights directly:

- **Access:** query your PostgreSQL database and `./chroma_db/`
- **Deletion:** `DROP DATABASE forgesdlc;` and `rm -rf ./chroma_db/`
- **Portability:** export your PostgreSQL database in standard SQL format

For questions: ag.chaudhari.1512@gmail.com

---

## Changes to This Policy

Material changes will be announced in the [CHANGELOG](../CHANGELOG.md) and
tagged in GitHub Releases. Continued use after 30 days constitutes acceptance.

---

## Open Source

forgeSDLC is open source (MIT License). You can inspect exactly what data is
collected and how at [github.com/Akash-1512/forgesdlc](https://github.com/Akash-1512/forgesdlc).