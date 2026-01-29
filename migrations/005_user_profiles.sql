-- User profiles: name, profile pic, locale, timezone, location (no consent required)
-- See Notion: "Capturing User Profile Info from Facebook Webhooks"

-- User profiles table
create table user_profiles (
  id uuid primary key default gen_random_uuid(),

  -- Facebook identifiers
  sender_id text not null unique,
  page_id text not null,

  -- Basic profile (no consent required)
  first_name text,
  last_name text,
  profile_pic text,
  locale text,
  timezone int,

  -- Location (if user shares via Messenger)
  location_lat double precision,
  location_long double precision,
  location_title text,
  location_address text,

  -- Interaction metadata
  first_interaction_at timestamptz default now(),
  last_interaction_at timestamptz default now(),
  total_messages int default 0,

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_user_profiles_page_sender on user_profiles(page_id, sender_id);
create index idx_user_profiles_sender on user_profiles(sender_id);
create index idx_user_profiles_last_interaction on user_profiles(last_interaction_at);
create index idx_user_profiles_location on user_profiles(location_lat, location_long)
  where location_lat is not null;

alter table message_history
  add column if not exists user_profile_id uuid references user_profiles(id);

create index if not exists idx_message_history_user_profile on message_history(user_profile_id);

create trigger update_user_profiles_updated_at
  before update on user_profiles
  for each row
  execute function update_updated_at_column();

create or replace function update_user_interaction()
returns trigger as $$
begin
  update user_profiles
  set
    last_interaction_at = now(),
    total_messages = total_messages + 1
  where sender_id = new.sender_id;
  return new;
end;
$$ language plpgsql;

create trigger update_user_interaction_on_message
  after insert on message_history
  for each row
  execute function update_user_interaction();
