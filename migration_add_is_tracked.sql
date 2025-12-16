-- Add is_tracked column to products table
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS is_tracked BOOLEAN DEFAULT FALSE;
