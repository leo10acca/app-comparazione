-- Add report settings columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS report_frequency TEXT DEFAULT 'Mai',
ADD COLUMN IF NOT EXISTS last_report_sent TIMESTAMP WITH TIME ZONE;
