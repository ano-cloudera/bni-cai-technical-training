from pathlib import Path

from bni_training.semantic import SemanticCatalog, compile_question


def main():
    catalog = SemanticCatalog.load(Path("semantic/credit_portfolio.yaml"))
    for question in ["What is the outstanding balance by region?", "Show delinquency rate by product id"]:
        print(question)
        print(compile_question(question, catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
