-- FuelGuard initial Supabase schema
-- Run this in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.stations (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    city text,
    payment_term_days integer not null default 0,
    color_key text,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    short_code text,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.tanks (
    id uuid primary key default gen_random_uuid(),
    station_id uuid not null references public.stations(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    capacity_liters numeric(12,2) not null default 0,
    capacity_per_tank_liters numeric(12,2) not null default 0,
    tank_count integer not null default 1,
    current_stock_liters numeric(12,2) not null default 0,
    daily_avg_liters numeric(12,2) not null default 0,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (station_id, product_id)
);

create table if not exists public.app_users (
    id uuid primary key default gen_random_uuid(),
    username text not null unique,
    name text not null,
    role text not null check (role in ('Sócio', 'Gerente')),
    password_hash text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_stations (
    user_id uuid not null references public.app_users(id) on delete cascade,
    station_id uuid not null references public.stations(id) on delete cascade,
    primary key (user_id, station_id)
);

create table if not exists public.stock_measurements (
    id uuid primary key default gen_random_uuid(),
    station_id uuid not null references public.stations(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    measured_at timestamptz not null default now(),
    stock_liters numeric(12,2) not null,
    source text not null default 'manual',
    created_by text,
    created_at timestamptz not null default now()
);

create table if not exists public.sales_uploads (
    id uuid primary key default gen_random_uuid(),
    station_id uuid references public.stations(id) on delete set null,
    product_id uuid references public.products(id) on delete set null,
    sale_date date,
    liters numeric(12,2) not null,
    source_file text,
    created_at timestamptz not null default now()
);

create table if not exists public.market_snapshots (
    id uuid primary key default gen_random_uuid(),
    captured_at timestamptz not null default now(),
    usd_brl numeric(12,4),
    usd_delta numeric(8,4),
    brent numeric(12,4),
    brent_delta numeric(8,4),
    trend text,
    source text
);

create table if not exists public.delivery_schedule (
    id uuid primary key default gen_random_uuid(),
    station_id uuid references public.stations(id) on delete set null,
    company_name text,
    product_id uuid references public.products(id) on delete set null,
    product_name text,
    delivery_date date not null,
    volume_liters numeric(12,2) not null,
    compartments integer not null default 0,
    score numeric(5,2),
    reason text,
    status text not null default 'programado',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.decision_history (
    id uuid primary key default gen_random_uuid(),
    decided_at timestamptz not null default now(),
    username text,
    decision text not null,
    total_volume_liters numeric(12,2) not null default 0,
    scheduled_orders integer not null default 0,
    simulated_result numeric(12,2) not null default 0,
    notes text
);

insert into public.products (name, short_code)
values
    ('Gasolina Comum', 'GC'),
    ('Etanol Comum', 'ET'),
    ('Gasolina Aditivada', 'GA'),
    ('Etanol Aditivado', 'EA'),
    ('Gasolina Podium', 'PODIUM'),
    ('Diesel Comum', 'DC'),
    ('Diesel Aditivado', 'DA')
on conflict (name) do nothing;
