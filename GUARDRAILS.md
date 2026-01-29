Define safety boundaries, validation rules, and risk mitigation strategies.

---

## Risk Classification

### Input Validation
- Reject inputs > **1000** characters (Facebook Messenger limit is 2000, but we enforce stricter limit)
- Blocklist: list of blocked keywords/patterns for prompt injection
- Jailbreak detection: use relevance classifier for suspicious patterns
- URL validation: Only allow HTTP/HTTPS URLs for website scraping
- Message rate limiting: Max 10 messages per user per minute

---

### Tool Risk Levels

| Tool | Risk | Guardrail | Human Approval? |
|------|------|-----------|-----------------|
| `scrape_website` | 🟢 LOW | URL validation, timeout limits | No |
| `build_reference_doc` | 🟢 LOW | Content size limits, hash verification | No |
| `get_bot_configuration` | 🟢 LOW | Read-only operation | No |
| `send_message` (Facebook) | 🟡 MEDIUM | Message validation, rate limiting | No |
| `agent_service.respond` | 🟡 MEDIUM | Confidence threshold, escalation flags | Conditional |
| `create_bot_configuration` | 🟠 HIGH | Validation + audit log | No (CLI only) |
| `update_bot_configuration` | 🟠 HIGH | Approval gate + audit log | **Yes** |
| `delete_bot_configuration` | 🔴 CRITICAL | Approval gate + 24hr delay | **Yes** |

---

### PII Handling

| Field | Policy |
|------|--------|
| Fields to redact | Facebook user IDs, phone numbers, email addresses (if detected) |
| Logging policy | Log message metadata but mask PII in logs |
| Data retention | Message history: 90 days, Bot configs: Indefinite (until deletion) |
| Facebook data | Only store message text and sender_id (no profile data) |

---

### Moderation & Safety

🛡️ **Use OpenAI Moderation API for:**
- Hate speech
- Violence/harm
- Harassment
- Self-harm content

**Custom safety classifier** for:
- Political misinformation detection
- Off-topic queries (outside reference document scope)
- Spam detection

**Response Filtering:**
- Agent responses must be under 300 characters (Facebook Messenger best practice)
- Escalate if confidence < 0.7
- Flag for human review if requires_escalation = True

---

## Escalation Rules

🚨 **When agent should hand off to human:**
- Confidence score < 0.7 for specific task
- Agent exceeds 3 retries for same message
- User provides conflicting/incomplete info
- Attempting high-risk action (config updates, deletions)
- Detected prompt injection attempt
- Message contains PII that needs special handling
- Response would exceed 300 characters (requires summarization)

**Escalation Actions:**
1. Log incident with full context
2. Set `requires_escalation = True` in AgentResponse
3. Send default message: "I'm not sure about that. Let me connect you with a team member who can help."
4. Create escalation ticket in monitoring system
5. Notify admin via configured alert channel

---

## Incident Response

How to detect, log, and respond to:

| Incident Type | Detection | Response |
|---------------|-----------|----------|
| Prompt injection attempts | Pattern matching (e.g., "ignore previous instructions", "system:", "you are now"), anomaly detection | Log + block + alert admin |
| System prompt leaks | Output scanning for internal prompts or system messages | Immediate termination + review + rotate tokens |
| Unauthorized tool access | Permission checks, page_id validation | Deny + audit log + alert |
| Hallucinations | Fact-checking against reference doc, confidence thresholds | Flag for review + escalate + update reference doc if needed |
| Rate limit exceeded | Message count tracking per sender_id | Throttle + return rate limit message |
| Copilot SDK failure | Health check failures, timeout errors | Automatic fallback to OpenAI + log incident |
| Facebook API errors | HTTP error codes, invalid token responses | Log + retry with exponential backoff + alert if persistent |
| Database connection failures | Connection timeout, query errors | Retry with backoff + fallback to cached configs + alert |

---

## Content Safety

### Message Content Validation

**Before Processing:**
- Check message length (max 1000 chars)
- Scan for blocklisted patterns
- Validate sender_id format
- Check rate limits

**During Processing:**
- Monitor for prompt injection patterns
- Track confidence scores
- Validate response length
- Check against reference document scope

**After Processing:**
- Sanitize response (remove any system prompts)
- Validate response format
- Check for PII leakage
- Log for audit trail

### Reference Document Safety

- Content must be from verified website URL
- Content hash verification to detect tampering
- Maximum document size: 50,000 characters
- Regular content updates to prevent staleness

---

## Monitoring & Alerting

### Key Metrics to Monitor
- Message processing latency (p50, p95, p99)
- Agent confidence scores (distribution)
- Escalation rate (% of messages requiring human)
- Copilot SDK availability and fallback rate
- Facebook API error rate
- Database query performance

### Alert Thresholds
- 🟡 Warning: Escalation rate > 20%
- 🟠 Critical: Copilot SDK unavailable > 5 minutes
- 🔴 Critical: Facebook API error rate > 10%
- 🔴 Critical: Database connection failures > 3 consecutive

---

## Compliance & Privacy

### Facebook Messenger Compliance
- Comply with Facebook Messenger Platform policies
- Respect user privacy and data protection
- Provide opt-out mechanisms
- Handle user data deletion requests

### Data Protection
- Encrypt sensitive data at rest (Supabase handles this)
- Use HTTPS for all external communications
- Rotate API keys and tokens regularly
- Audit log access to sensitive operations
