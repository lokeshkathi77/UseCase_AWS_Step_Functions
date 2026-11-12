# EC2 test data

`transactions_test.csv` contains four valid rows and six rejected rows:

- one negative amount
- one non-numeric amount
- one unsupported status
- one duplicate `tid`
- one invalid date
- one missing amount

Expected valid transaction count: `4`

Expected rejected transaction count: `6`

The expected ECS summary is stored in `expected_summary.json`.
