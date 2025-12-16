-- Add columns for price comparison
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS competitor_price NUMERIC,
ADD COLUMN IF NOT EXISTS price_gap NUMERIC,
ADD COLUMN IF NOT EXISTS last_check TIMESTAMP WITH TIME ZONE;
