-- Initial database schema for Facebook Messenger AI Bot
-- Supabase PostgreSQL migration

-- Bot configurations table
-- Stores configuration for each Facebook Page bot instance
create table bot_configurations (
  id uuid primary key default gen_random_uuid(),
  page_id text not null unique,
  website_url text not null,
  reference_doc_id uuid not null,
  tone text not null,
  facebook_page_access_token text not null,
  facebook_verify_token text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  is_active boolean default true
);

-- Reference documents table
-- Stores synthesized reference documents created from scraped website content
create table reference_documents (
  id uuid primary key default gen_random_uuid(),
  bot_id uuid not null references bot_configurations(id) on delete cascade,
  content text not null,
  source_url text not null,
  content_hash text not null,
  created_at timestamptz default now()
);

-- Message history table
-- Stores conversation history for analytics and debugging
create table message_history (
  id uuid primary key default gen_random_uuid(),
  bot_id uuid not null references bot_configurations(id) on delete cascade,
  sender_id text not null,
  message_text text not null,
  response_text text not null,
  confidence float,
  requires_escalation boolean default false,
  created_at timestamptz default now()
);

-- Indexes for performance
create index idx_bot_configurations_page_id on bot_configurations(page_id);
create index idx_bot_configurations_is_active on bot_configurations(is_active);
create index idx_reference_documents_bot_id on reference_documents(bot_id);
create index idx_message_history_bot_id on message_history(bot_id);
create index idx_message_history_sender_id on message_history(sender_id);
create index idx_message_history_created_at on message_history(created_at);

-- Function to update updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Trigger to automatically update updated_at on bot_configurations
create trigger update_bot_configurations_updated_at
  before update on bot_configurations
  for each row
  execute function update_updated_at_column();
