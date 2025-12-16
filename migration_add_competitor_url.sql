-- Add competitor_url column to products table
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS competitor_url TEXT;
