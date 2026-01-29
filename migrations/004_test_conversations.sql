-- Test conversation persistence for setup test REPL.
-- test_sessions: one per REPL invocation (config); test_messages: one per user/bot exchange.

CREATE TABLE test_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reference_doc_id uuid NOT NULL REFERENCES reference_documents(id) ON DELETE CASCADE,
  source_url text NOT NULL,
  tone text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE test_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  test_session_id uuid NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
  user_message text NOT NULL,
  response_text text NOT NULL,
  confidence float,
  requires_escalation boolean DEFAULT false,
  escalation_reason text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_test_sessions_reference_doc_id ON test_sessions(reference_doc_id);
CREATE INDEX idx_test_sessions_created_at ON test_sessions(created_at);
CREATE INDEX idx_test_messages_test_session_id ON test_messages(test_session_id);
CREATE INDEX idx_test_messages_created_at ON test_messages(created_at);
