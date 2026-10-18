-- Replace ${CSV_NFS_ROOT} with the approved shared path. Skip one header line during the staging step.
LOAD DATA INPATH '${CSV_NFS_ROOT}/branch_master.csv' OVERWRITE INTO TABLE bni_training.branch_master;
LOAD DATA INPATH '${CSV_NFS_ROOT}/product_master.csv' OVERWRITE INTO TABLE bni_training.product_master;
LOAD DATA INPATH '${CSV_NFS_ROOT}/customers.csv' OVERWRITE INTO TABLE bni_training.customers;
LOAD DATA INPATH '${CSV_NFS_ROOT}/loan_applications.csv' OVERWRITE INTO TABLE bni_training.loan_applications;
LOAD DATA INPATH '${CSV_NFS_ROOT}/loan_accounts.csv' OVERWRITE INTO TABLE bni_training.loan_accounts;
LOAD DATA INPATH '${CSV_NFS_ROOT}/repayment_transactions.csv' OVERWRITE INTO TABLE bni_training.repayment_transactions;

