# Synthetic Data Dictionary

All records are deterministic synthetic workshop data. They have no relationship to BNI customers, staff, branches, or products.

| Dataset | Grain | Key fields | Workshop use |
|---|---|---|---|
| `branch_master` | One synthetic branch | `branch_id`, `region` | Regional grouping |
| `product_master` | One synthetic product | `product_id`, `product_type` | Product grouping |
| `customers` | One synthetic customer | `customer_id`, `customer_segment` | Segment analysis |
| `loan_applications` | One synthetic application | `application_id`, `status`, amounts | Approval analysis |
| `loan_accounts` | One synthetic account | `account_id`, balance, DPD, risk band | Exposure and delinquency |
| `repayment_transactions` | One synthetic payment | `transaction_id`, scheduled and actual amount | Repayment trends |

Synthetic identifiers use fixed prefixes such as `CUST`, `APP`, `ACC`, and `TXN`. The application must never treat these records as lending decisions.

