-- Scraped pages index: per-page metadata and vector embeddings for semantic search
-- Requires pgvector extension (Supabase has it built-in)

create extension if not exists vector;

-- Per-page metadata and content from scraped websites
create table scraped_pages (
  id uuid primary key default gen_random_uuid(),
  reference_doc_id uuid not null references reference_documents(id) on delete cascade,
  url text not null,
  normalized_url text not null,
  title text,
  raw_content text not null,
  word_count int not null,
  scraped_at timestamptz not null,
  created_at timestamptz default now()
);

-- Chunks with vector embeddings for semantic search
create table page_chunks (
  id uuid primary key default gen_random_uuid(),
  scraped_page_id uuid not null references scraped_pages(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding vector(1536) not null,
  word_count int not null,
  created_at timestamptz default now()
);

-- Indexes
create index idx_scraped_pages_reference_doc_id on scraped_pages(reference_doc_id);
create unique index idx_scraped_pages_normalized_url_reference_doc
  on scraped_pages(normalized_url, reference_doc_id);

-- IVFFlat index for approximate nearest-neighbor search (cosine distance)
-- lists = 100 is a reasonable default for small-to-medium datasets
create index idx_page_chunks_embedding_cosine on page_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index idx_page_chunks_scraped_page_id on page_chunks(scraped_page_id);

-- RPC for semantic search: returns chunks with source URL, ordered by cosine distance.
-- query_embedding_text is a string like '[0.1, 0.2, ...]' so Supabase/PostgREST can pass it.
create or replace function search_page_chunks(
  query_embedding_text text,
  ref_doc_id uuid,
  match_limit int default 5
)
returns table (
  id uuid,
  scraped_page_id uuid,
  chunk_index int,
  content text,
  word_count int,
  page_url text,
  distance float
)
language sql stable
as $$
  select
    pc.id,
    pc.scraped_page_id,
    pc.chunk_index,
    pc.content,
    pc.word_count,
    sp.url as page_url,
    (pc.embedding <=> query_embedding_text::vector(1536)) as distance
  from page_chunks pc
  join scraped_pages sp on sp.id = pc.scraped_page_id
  where sp.reference_doc_id = search_page_chunks.ref_doc_id
  order by pc.embedding <=> query_embedding_text::vector(1536)
  limit match_limit;
$$;
