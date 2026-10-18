SELECT 'branch_master' AS table_name, COUNT(*) AS row_count FROM bni_training.branch_master
UNION ALL SELECT 'product_master', COUNT(*) FROM bni_training.product_master
UNION ALL SELECT 'customers', COUNT(*) FROM bni_training.customers
UNION ALL SELECT 'loan_applications', COUNT(*) FROM bni_training.loan_applications
UNION ALL SELECT 'loan_accounts', COUNT(*) FROM bni_training.loan_accounts
UNION ALL SELECT 'repayment_transactions', COUNT(*) FROM bni_training.repayment_transactions;

