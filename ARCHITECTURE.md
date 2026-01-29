# Architecture

Define your agent system's structure, decision flows, and component interactions.

---

## System Overview

The Facebook Messenger AI Bot is a production-ready FastAPI application that creates AI-powered Facebook Messenger bots. The system uses a single-agent architecture with PydanticAI, powered by GitHub Copilot SDK (with OpenAI fallback), to answer questions based on synthesized reference documents from scraped websites.

**High-Level Flow:**
```
Facebook Messenger → Webhook → FastAPI → Agent Service → Copilot SDK → Response → Facebook Messenger
```

**Key Components:**
- **FastAPI Application**: Webhook endpoints for Facebook Messenger
- **PydanticAI Agent**: Message processing and response generation
- **Copilot SDK Service**: LLM operations with fallback
- **Scraper Service**: Website content extraction
- **Reference Document Service**: Content synthesis
- **Supabase Database**: Configuration and message history storage
- **Facebook Service**: Message sending via Graph API

---

## Agent Roles & Responsibilities

| Agent Name | Purpose | Tools | Output |
|------------|---------|-------|--------|
| MessengerAgentService | Process user messages and generate responses | CopilotService (chat), Reference Document (read), Message History (read) | AgentResponse (message, confidence, escalation flags) |

**Single Agent Architecture:**
- One primary agent handles all message processing
- Agent uses reference document as knowledge base
- Agent maintains conversation context via recent messages
- Agent escalates to human when confidence is low or out of scope

---

## Decision Flow

```
User Message (Facebook Messenger)
    ↓
Webhook Endpoint (FastAPI)
    ↓
Parse Message & Extract sender_id, page_id
    ↓
Lookup Bot Configuration (Supabase)
    ↓
Build AgentContext (reference_doc + tone + recent_messages)
    ↓
MessengerAgentService.respond()
    ↓
    ├─→ Low Confidence (< 0.7) → Escalate to Human
    ├─→ Out of Scope → Escalate to Human
    └─→ Valid Response → Send via Facebook Graph API
    ↓
Save to Message History (Supabase)
```

**Setup Flow:**
```
CLI Setup Command
    ↓
Scrape Website → Text Chunks
    ↓
Copilot SDK: Synthesize Reference Document
    ↓
Store Reference Document (Supabase)
    ↓
Create Bot Configuration (Supabase)
    ↓
Ready for Messages
```

---

## Data Flow

### Input Schemas

**Webhook Payload:**
```python
class MessengerWebhookPayload(BaseModel):
    object: str
    entry: list[dict]  # Facebook webhook entry structure
```

**Message Input:**
```python
class MessengerMessageIn(BaseModel):
    sender_id: str
    recipient_id: str
    text: str | None
    timestamp: int
```

### State Management

**AgentContext:**
```python
class AgentContext(BaseModel):
    bot_config_id: str
    reference_doc: str  # Full markdown reference document
    tone: str  # Communication tone (professional, friendly, etc.)
    recent_messages: list[str]  # Last 3 messages for context
```

**AgentResponse:**
```python
class AgentResponse(BaseModel):
    message: str  # Response text (max 300 chars)
    confidence: float  # 0.0 to 1.0
    requires_escalation: bool
    escalation_reason: str | None
```

### Output Formats

- **Success**: AgentResponse with message and confidence > 0.7
- **Escalation**: AgentResponse with requires_escalation = True
- **Error**: HTTPException with appropriate status code

---

## Orchestration Pattern

**Used Pattern:** Single-agent with tools

**Reasoning:**
- Simple use case: Answer questions based on reference document
- No need for complex multi-agent coordination
- Single agent can handle all message types
- Easier to maintain and debug
- Lower latency (no agent handoffs)

**Agent Tools:**
1. **CopilotService.chat()**: LLM chat interface
2. **Reference Document Access**: Read-only access to synthesized content
3. **Message History**: Read recent conversation context
4. **Facebook Service**: Send messages (called after agent response)

---

## Tools & External Systems

### Tool Registry

| Tool | Risk | Description |
|------|------|-------------|
| `scrape_website` | 🟢 LOW | Read-only website scraping, timeout limits |
| `build_reference_doc` | 🟢 LOW | Content synthesis via Copilot SDK |
| `get_bot_configuration` | 🟢 LOW | Read-only database query |
| `get_reference_document` | 🟢 LOW | Read-only database query |
| `agent_service.respond` | 🟡 MEDIUM | AI response generation, confidence-based |
| `send_message` (Facebook) | 🟡 MEDIUM | Send message via Facebook Graph API |
| `save_message_history` | 🟡 MEDIUM | Write message to database |
| `create_bot_configuration` | 🟠 HIGH | Create new bot (CLI only, requires validation) |

### External Systems

**GitHub Copilot SDK:**
- Primary LLM provider
- Endpoint: `COPILOT_CLI_HOST` (default: http://localhost:5909)
- Fallback: OpenAI API if Copilot unavailable
- Operations: Chat completion, content synthesis

**Facebook Graph API:**
- Send messages to users
- Endpoint: `https://graph.facebook.com/v18.0/me/messages`
- Authentication: Page Access Token
- Rate limits: Handled by Facebook

**Supabase (PostgreSQL):**
- Database for bot configurations
- Reference documents storage
- Message history logging
- Connection: Via Supabase Python client

---

## Error Recovery & Fallback Logic

### Copilot SDK Failures

**Detection:**
- Health check failures
- HTTP timeout errors
- Invalid response format

**Recovery:**
1. Check `copilot.is_available()` before use
2. If unavailable, automatically fallback to OpenAI
3. Log fallback event for monitoring
4. Continue processing with OpenAI

**Fallback Implementation:**
```python
async def chat(self, system_prompt: str, messages: list[dict]) -> str:
    if not await self.is_available():
        logger.warning("Copilot SDK unavailable, using OpenAI fallback")
        return await self._fallback_to_openai(system_prompt, messages)
    # ... use Copilot SDK
```

### Facebook API Failures

**Detection:**
- HTTP error codes (4xx, 5xx)
- Invalid token responses
- Rate limit errors

**Recovery:**
1. Retry with exponential backoff (max 3 retries)
2. Log error for monitoring
3. If persistent, alert admin
4. Continue processing (don't block other messages)

### Database Failures

**Detection:**
- Connection timeouts
- Query errors
- Transaction failures

**Recovery:**
1. Retry with backoff (max 3 retries)
2. Use cached bot configurations if available
3. Log error for monitoring
4. Alert admin if persistent

### Agent Response Failures

**Detection:**
- Low confidence scores (< 0.7)
- Out-of-scope queries
- Invalid response format

**Recovery:**
1. Set `requires_escalation = True`
2. Return default escalation message
3. Log for human review
4. Continue processing other messages

---

## Component Interactions

### Request Flow

```
┌─────────────────┐
│ Facebook        │
│ Messenger       │
└────────┬────────┘
         │ POST /webhook
         ↓
┌─────────────────┐
│ FastAPI         │
│ Webhook Handler │
└────────┬────────┘
         │
         ├─→ Parse payload
         ├─→ Extract page_id
         │
         ↓
┌─────────────────┐
│ Repository      │
│ (Supabase)      │
└────────┬────────┘
         │
         ├─→ Get bot_config
         ├─→ Get reference_doc
         ├─→ Get recent messages
         │
         ↓
┌─────────────────┐
│ Agent Service   │
│ (PydanticAI)    │
└────────┬────────┘
         │
         ├─→ Build context
         ├─→ Call Copilot SDK
         ├─→ Generate response
         │
         ↓
┌─────────────────┐
│ Facebook        │
│ Service         │
└────────┬────────┘
         │
         ├─→ Send message
         │
         ↓
┌─────────────────┐
│ Repository      │
│ (Save history)  │
└─────────────────┘
```

### Setup Flow

```
┌─────────────────┐
│ CLI Setup       │
└────────┬────────┘
         │
         ├─→ Get website URL
         │
         ↓
┌─────────────────┐
│ Scraper Service │
└────────┬────────┘
         │
         ├─→ Scrape website
         ├─→ Chunk text
         │
         ↓
┌─────────────────┐
│ Copilot Service │
└────────┬────────┘
         │
         ├─→ Synthesize reference doc
         │
         ↓
┌─────────────────┐
│ Repository      │
│ (Save config)   │
└─────────────────┘
```

---

## Scalability Considerations

### Current Architecture
- Single FastAPI instance
- Single agent per message
- Direct database connections
- Synchronous message processing

### Future Scaling Options
- **Horizontal Scaling**: Multiple FastAPI instances behind load balancer
- **Message Queue**: Use Redis/RabbitMQ for async message processing
- **Caching**: Redis cache for bot configurations
- **Database Connection Pooling**: Supabase connection pooling
- **Agent Pooling**: Multiple agent instances for concurrent processing

---

## Security Architecture

### Authentication & Authorization
- Facebook webhook verification via verify_token
- Page Access Token validation
- Supabase service key for database access

### Data Protection
- Environment variables for secrets
- Encrypted database connections (Supabase)
- HTTPS for all external communications
- PII masking in logs

### Input Validation
- Pydantic models for all inputs
- URL validation for website scraping
- Message length limits
- Rate limiting per user
