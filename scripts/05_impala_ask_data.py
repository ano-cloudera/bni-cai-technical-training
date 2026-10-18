from bni_training.backends.factory import create_backend
from bni_training.config import Settings


def main():
    settings = Settings.load()
    backend = create_backend(settings)
    result = backend.execute(
        "SELECT region, SUM(outstanding_balance) AS exposure "
        "FROM loan_accounts GROUP BY region ORDER BY exposure DESC LIMIT 10",
        30,
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
