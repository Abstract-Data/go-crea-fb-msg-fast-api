-- Multi-tenant support migration
-- Adds tenant tracking for SaaS model

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    email text,
    paig_project_id text,  -- Link to PydanticAI Gateway project
    monthly_budget_cents integer DEFAULT 10000,  -- $100 default
    plan text DEFAULT 'free',  -- free, pro, enterprise
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Add tenant_id to existing tables
ALTER TABLE bot_configurations 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

ALTER TABLE reference_documents 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

ALTER TABLE message_history 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

-- Create usage tracking table
CREATE TABLE IF NOT EXISTS usage_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    bot_id uuid REFERENCES bot_configurations(id) ON DELETE CASCADE,
    model text NOT NULL,
    tokens_in integer DEFAULT 0,
    tokens_out integer DEFAULT 0,
    cost_cents numeric(10,4) DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email);
CREATE INDEX IF NOT EXISTS idx_bot_configurations_tenant_id ON bot_configurations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_tenant_id ON usage_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at);

-- Trigger for tenants updated_at
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
