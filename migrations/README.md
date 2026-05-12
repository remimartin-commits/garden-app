# Manual Database Migrations

## Naming Convention

YYYY-MM-DD_HHMM_description.sql

Example: 2025-05-12_0754_add_fuel_cost.sql

## Workflow

1. Write the SQL file in Cursor

2. Commit and push to GitHub

3. SSH to VPS and run: psql -U garden_user -d garden_db -f migrations/XXXX.sql

4. Mark the file as APPLIED in this README

## Applied Migrations

- [x] 2025-05-12_0754_add_fuel_cost.sql — Added fuel_cost DOUBLE PRECISION DEFAULT 10.0 to customers