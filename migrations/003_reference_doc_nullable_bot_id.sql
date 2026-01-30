-- Allow reference_documents to exist before a bot is created (resume setup).
-- Setup CLI saves the reference document right after scrape/build; bot_id is
-- set when create_bot_configuration runs and link_reference_document_to_bot is called.
ALTER TABLE reference_documents
ALTER COLUMN bot_id DROP NOT NULL;
