# EU AI Act Compliance Checklist — forgeSDLC

**Regulation:** EU AI Act (Regulation 2024/1689)
**Effective date:** August 2, 2026 (GPAI obligations)
**Last updated:** April 2026
**Owner:** Akash Chaudhari

---

## Classification

**Category:** GPAI System (General-Purpose AI System)
**Article:** Article 3(63) — system trained on large amounts of data, capable of
serving multiple purposes

**NOT high-risk (Article 6):** forgeSDLC does not:
- Make or assist in decisions affecting fundamental rights
- Process biometric data
- Operate in critical infrastructure, education, employment, or healthcare
- Target vulnerable groups

forgeSDLC is a developer productivity tool. It orchestrates LLM APIs and
generates software artifacts for consenting adult developers.

---

## GPAI Obligations (Articles 52–55)

### Article 52 — Transparency

- [x] **Users informed they interact with AI:** README, HITL panel, and interpret
      records make AI involvement explicit at every step
- [x] **No deception:** forgeSDLC clearly identifies all AI-generated content
      via InterpretRecord audit trail
- [x] **HITL gates:** every architectural/deployment decision requires human
      approval ("100% GO") — AI does not act autonomously

### Article 53 — GPAI Model Obligations

- [x] **Training data disclosure:** forgeSDLC uses OpenAI, Groq, Google, and
      Anthropic APIs. These providers' training data is documented in their
      respective model cards. forgeSDLC does not train models.
- [x] **Copyright policy:** forgeSDLC does not train on user code. User code
      is processed in-context per request only.
- [ ] **Technical documentation (model card):** **PENDING — due before Aug 2, 2026**
      Document forgeSDLC's GPAI classification, capabilities, and limitations.
- [ ] **Published on GitHub:** **PENDING — before Aug 2, 2026**

### Article 54 — Systemic Risk Assessment

Not applicable. forgeSDLC does not meet the FLOP threshold for systemic risk
classification (10^25 FLOPs training compute). forgeSDLC uses third-party APIs,
it does not train foundation models.

### Article 55 — Serious Incident Reporting

- [x] **Incident response:** serious incidents (data breach, unintended code
      execution) reported to relevant national authority within 3 business days
- [x] **Contact:** ag.chaudhari.1512@gmail.com

---

## Pending Actions

| Action | Deadline | Owner |
|--------|----------|-------|
| Publish model card on GitHub | August 1, 2026 | Akash |
| Technical documentation (Article 53) | August 1, 2026 | Akash |
| Review provider sub-processor agreements | June 1, 2026 | Akash |

---

## Days Until Deadline

Run: `python -c "from datetime import date; print((date(2026,8,2)-date.today()).days, 'days')`