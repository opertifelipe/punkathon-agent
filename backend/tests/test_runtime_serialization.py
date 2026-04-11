from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from punkathon_agent.punkagent.runtime import _normalize_conversation, serialize_conversation


class _ParsedPayload(BaseModel):
    title: str
    description: str


class _NestedPayload(BaseModel):
    output: list[dict[str, str]]


class RuntimeSerializationTests(unittest.TestCase):
    def test_serialize_conversation_drops_parsed_payloads_from_ai_messages(self) -> None:
        message = AIMessage(
            content="Risposta finale",
            additional_kwargs={
                "parsed": _ParsedPayload(title="Trend", description="Desc"),
                "kept": _NestedPayload(output=[{"type": "message", "phase": "final_answer"}]),
            },
            response_metadata={
                "raw": _NestedPayload(output=[{"type": "message", "phase": "final_answer"}]),
            },
        )

        serialized = serialize_conversation([message])

        self.assertEqual(len(serialized), 1)
        data = serialized[0]["data"]
        self.assertNotIn("parsed", data["additional_kwargs"])
        self.assertEqual(data["additional_kwargs"]["kept"]["output"][0]["phase"], "final_answer")
        self.assertEqual(data["response_metadata"]["raw"]["output"][0]["type"], "message")

    def test_serialize_conversation_round_trips_sanitized_messages(self) -> None:
        messages = [
            HumanMessage(content="ciao"),
            AIMessage(content="ok", additional_kwargs={"parsed": _ParsedPayload(title="x", description="y")}),
        ]

        serialized = serialize_conversation(messages)
        normalized = _normalize_conversation(serialized)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0].content, "ciao")
        self.assertEqual(normalized[1].content, "ok")


if __name__ == "__main__":
    unittest.main()