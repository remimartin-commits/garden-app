-- Migration: add fuel_cost to customers
-- Applied on VPS: 2025-05-12
-- Author: Cursor

ALTER TABLE customers
ADD COLUMN fuel_cost DOUBLE PRECISION NOT NULL DEFAULT 10.0;