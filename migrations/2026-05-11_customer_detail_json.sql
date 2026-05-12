-- Customer photo attachments (JSON blob). Safe to run once; ignore if column exists.
ALTER TABLE customers ADD COLUMN detail_json TEXT;
