from bni_training.config import validate_group_id
from bni_training.guardrails import validate_input


class CreditInsightService:
    def __init__(self, group_id: str, workflow):
        self.group_id = validate_group_id(group_id)
        self.workflow = workflow

    def ask(self, question: str):
        return self.workflow.run(validate_input(question))
