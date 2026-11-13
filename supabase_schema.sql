-- Run this in your Supabase Dashboard -> SQL Editor -> New Query
-- Creates per-user option positions table with strict Row Level Security (RLS)

create table if not exists public.positions (
    id text primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    side text not null check (side in ('SELL', 'BUY')),
    type text not null check (type in ('CE', 'PE')),
    strike integer not null,
    expiry text not null,
    lots integer not null check (lots > 0),
    qty integer not null check (qty > 0),
    entry_price numeric not null default 0,
    exit_price numeric not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.positions enable row level security;

create policy "Users can view own positions"
    on public.positions for select
    using (auth.uid() = user_id);

create policy "Users can insert own positions"
    on public.positions for insert
    with check (auth.uid() = user_id);

create policy "Users can update own positions"
    on public.positions for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users can delete own positions"
    on public.positions for delete
    using (auth.uid() = user_id);
