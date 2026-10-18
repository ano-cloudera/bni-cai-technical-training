from pathlib import Path

from bni_training.backends.factory import create_backend
from bni_training.config import Settings
from bni_training.crew import CreditInsightWorkflow
from bni_training.semantic import SemanticCatalog
from bni_training.tools.data_tool import DataQueryTool


class DemoNarrator:
    def summarize(self, question, result):
        return f"The synthetic query returned {result.row_count} grouped portfolio rows."


def main():
    settings = Settings.load()
    tool = DataQueryTool(
        create_backend(settings), SemanticCatalog.load(Path("semantic/credit_portfolio.yaml"))
    )
    print(
        CreditInsightWorkflow(tool, DemoNarrator())
        .run("What is the outstanding balance by region?")
        .model_dump_json(indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
