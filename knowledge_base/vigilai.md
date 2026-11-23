# VigilAI Assistant

## What VigilAI is
VigilAI is the assistant built into VigilOps. It opens from the floating chat icon at the bottom-right of every page. It uses Google Gemini through the backend, together with the VigilOps knowledge base and authorised live platform data.

## What VigilAI can help with
Explaining monitoring, alerts, incidents, security rules SEC-001 to SEC-005, remediation workflows, roles and permissions, audit logs, architecture, APIs and configuration; summarising your open incidents, findings and remediation requests; and suggesting troubleshooting steps.

## What VigilAI cannot do
VigilAI is read-only. It cannot approve, reject or execute remediation, run scans or shell commands, change incidents, configurations, users or roles, or access secrets. It only answers questions about VigilOps and refuses unrelated requests such as general knowledge, jokes or poems.

## How VigilAI answers
1) The backend checks that the question is about VigilOps. 2) It retrieves matching sections from the knowledge base. 3) It calls fixed read-only functions for live data, limited by your role. 4) It sends the question with that context to Gemini. 5) The reply is validated and sanitised before it is shown. Statements from live data are labelled "Live platform data" and general advice "General guidance".

## Safeguards
Backend scope validation, restricted knowledge retrieval, authorised live-data functions, role-aware access checks, minimised context, prompt-injection resistance, response validation, output sanitisation and per-user rate limiting. Documentation, incident text and user input are treated as untrusted data.

## Documentation fallback
If Gemini is not configured, is unreachable, times out or its free quota is exhausted, VigilAI answers directly from the documentation and live platform data and states that live AI generation is temporarily unavailable.

## Privacy and usage logging
VigilAI logs usage metadata (time, mode, token counts, which sources were used) but not the text of questions or answers. Chat history is kept only in the browser for the current session.
