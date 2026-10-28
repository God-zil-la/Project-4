import ast
import inspect
from pathlib import Path
from unittest import TestCase

from ai_assistant.bots.chat_service import process_bot_message


class ChatContractTests(TestCase):
    def test_message_id_is_opt_in(self):
        signature = inspect.signature(process_bot_message)
        self.assertIn("return_message_id", signature.parameters)
        self.assertIs(
            signature.parameters["return_message_id"].default,
            False,
        )

    def test_both_return_paths_capture_saved_id(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "bots"
            / "chat_service.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "process_bot_message"
        )

        captured = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "saved_message_id"
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_save_chat_exchange"
        ]

        self.assertEqual(len(captured), 2)

        opt_in_assignments = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "result"
                for target in node.targets
            )
            and isinstance(node.value, ast.Name)
            and node.value.id == "saved_message_id"
        ]

        self.assertEqual(len(opt_in_assignments), 2)
