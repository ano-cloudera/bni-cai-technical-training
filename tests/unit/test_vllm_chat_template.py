"""The patched Qwen3.5 chat template accepts a system message after the first message and renders everything else as before."""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest

TEMPLATE = Path("config/vllm/qwen3_5_chat_template.jinja")


def render(messages, **extra) -> str:
    def raise_exception(message):
        raise jinja2.exceptions.TemplateError(message)

    env = jinja2.Environment(trim_blocks=False, lstrip_blocks=False)
    env.globals["raise_exception"] = raise_exception
    return env.from_string(TEMPLATE.read_text()).render(messages=messages, **extra)


def test_the_normal_conversation_is_rendered_as_qwen_expects() -> None:
    text = render(
        [{"role": "system", "content": "Rules."}, {"role": "user", "content": "Hi"}],
        add_generation_prompt=True,
        enable_thinking=False,
    )
    assert text == (
        "<|im_start|>system\nRules.<|im_end|>\n<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def test_a_later_system_message_is_rendered_instead_of_rejected() -> None:
    text = render(
        [
            {"role": "system", "content": "First rules."},
            {"role": "user", "content": "Question"},
            {"role": "system", "content": "Reminder from the framework."},
            {"role": "user", "content": "Follow-up"},
        ],
        add_generation_prompt=True,
    )
    assert text.count("<|im_start|>system\n") == 2
    assert text.index("Reminder from the framework.") > text.index("Question")
    assert text.endswith("<|im_start|>assistant\n<think>\n")


def test_a_conversation_that_starts_with_a_user_message_still_works() -> None:
    assert "<|im_start|>user\nHi<|im_end|>" in render([{"role": "user", "content": "Hi"}])


def test_other_errors_of_the_original_template_remain() -> None:
    with pytest.raises(jinja2.exceptions.TemplateError, match="No messages provided"):
        render([])
    with pytest.raises(jinja2.exceptions.TemplateError, match="No user query found"):
        render([{"role": "system", "content": "Only rules"}])
