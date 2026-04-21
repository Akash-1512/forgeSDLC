# Data Processing Agreement — forgeSDLC

**Template version:** 1.0
**For:** Enterprise customers in EU/UK/EEA
**Governing law:** GDPR (Regulation 2016/679)

---

## Parties

**Data Controller:** [Customer legal entity name and address]

**Data Processor:** Akash Chaudhari, trading as forgeSDLC
  Contact: ag.chaudhari.1512@gmail.com

---

## 1. Subject Matter

forgeSDLC processes personal data on behalf of the Controller solely to provide
the forgeSDLC SDLC orchestration service as described in the Order Form.

---

## 2. Nature and Purpose of Processing

| Category | Purpose | Legal Basis |
|----------|---------|-------------|
| Pipeline metadata (project IDs, run IDs, timestamps) | Service delivery, audit trail | Contract performance |
| User prompts (sent to LLM APIs) | AI-assisted code generation | Legitimate interests |
| API key references (OS keychain handle only, never the key value) | Authentication | Contract performance |

**NOT processed by forgeSDLC:** source code content, personal data in user
prompts beyond what the user explicitly provides, biometric data.

---

## 3. Data Location

All data processed by forgeSDLC resides in infrastructure **controlled by the
Controller**:

- **PostgreSQL database:** hosted by Controller (local Docker, Supabase, or
  Controller's cloud account)
- **ChromaDB vector store:** local filesystem at `./chroma_db/` on Controller's
  infrastructure
- **API keys:** Controller's OS keychain (macOS Keychain, Windows Credential
  Manager, Linux Secret Service)

forgeSDLC does not operate central servers that receive or store Controller data.

---

## 4. Sub-Processors

The Controller authorises the following sub-processors, used only when
the Controller configures forgeSDLC to use them:

| Sub-Processor | Purpose | Location |
|---------------|---------|----------|
| OpenAI, Inc. | LLM inference (gpt-5.4, gpt-5.4-mini) | USA |
| Groq, Inc. | LLM inference (llama-3.x) | USA |
| Google LLC | LLM inference (gemini-3.1) | USA |
| Anthropic, PBC | LLM inference (claude-sonnet) | USA |

Controller must review each sub-processor's DPA before enabling the
corresponding provider in forgeSDLC.

---

## 5. Security Measures

- API keys stored in OS-level keychain — never in plaintext
- All LLM API calls made over TLS 1.3
- PostgreSQL connection encrypted in transit
- Audit trail (InterpretRecord) logged locally — no external telemetry

---

## 6. Data Subject Rights

The Controller is responsible for responding to data subject requests.
forgeSDLC will assist the Controller within 5 business days of written request.

---

## 7. Retention and Deletion

Controller controls all data retention. forgeSDLC does not retain any Controller
data. Upon termination, the Controller deletes their PostgreSQL database and
`./chroma_db/` directory.

---

## 8. Signatures

| Party | Signature | Date |
|-------|-----------|------|
| Controller | | |
| Processor (Akash Chaudhari) | | |

---

*This template must be reviewed by qualified legal counsel before use.*