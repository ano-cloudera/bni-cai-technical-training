USE bni_training;
CREATE EXTERNAL TABLE IF NOT EXISTS branch_master (branch_id STRING, branch_name STRING, region STRING) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;
CREATE EXTERNAL TABLE IF NOT EXISTS product_master (product_id STRING, product_name STRING, product_type STRING) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;
CREATE EXTERNAL TABLE IF NOT EXISTS customers (customer_id STRING, customer_segment STRING, region STRING, branch_id STRING) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;
CREATE EXTERNAL TABLE IF NOT EXISTS loan_applications (application_id STRING, customer_id STRING, product_id STRING, application_date DATE, status STRING, requested_amount DECIMAL(18,2), approved_amount DECIMAL(18,2)) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;
CREATE EXTERNAL TABLE IF NOT EXISTS loan_accounts (account_id STRING, application_id STRING, customer_id STRING, branch_id STRING, region STRING, customer_segment STRING, product_id STRING, open_date DATE, outstanding_balance DECIMAL(18,2), dpd INT, risk_band STRING, account_status STRING) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;
CREATE EXTERNAL TABLE IF NOT EXISTS repayment_transactions (transaction_id STRING, account_id STRING, payment_date DATE, scheduled_amount DECIMAL(18,2), actual_amount DECIMAL(18,2)) ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' STORED AS TEXTFILE;

