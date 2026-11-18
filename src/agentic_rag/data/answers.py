"""Logical answers and immutable run references shared by both repositories."""

from typing import Any
from uuid import uuid4

from agentic_rag.data.repository import ConflictError
from agentic_rag.models.run import Run


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_user = None
    for message in messages:
        if message["role"] == "user":
            previous_user = message["id"]
        else:
            message.setdefault("parent_user_message_id", previous_user)
            if not message.get("versions") and message.get("run_id"):
                message["versions"] = [
                    {
                        "run_id": message["run_id"],
                        "status": message.get("status", "completed"),
                        "created_at": message["created_at"],
                    }
                ]
    return messages


def latest_answer(session: dict[str, Any], message_id: str) -> dict[str, Any]:
    messages = normalize_messages(session["messages"])
    if not messages or messages[-1]["role"] != "assistant" or messages[-1]["id"] != message_id:
        raise ConflictError("Only the latest reply can be changed")
    return messages[-1]


def prepare_answer(session: dict[str, Any], run: Run, user: dict[str, Any] | None) -> None:
    messages = normalize_messages(session["messages"])
    if run.regeneration_of_run_id:
        answer = latest_answer(session, str(run.assistant_message_id))
        if answer.get("run_id") != run.regeneration_of_run_id:
            raise ConflictError("The selected answer changed. Refresh this conversation and retry.")
        run.user_message_id = answer.get("parent_user_message_id")
    else:
        if user:
            run.user_message_id = str(user["id"])
            messages.append(user)
        run.assistant_message_id = run.assistant_message_id or uuid4().hex
        answer = {
            "id": run.assistant_message_id,
            "role": "assistant",
            "content": "",
            "status": "pending",
            "run_id": run.id,
            "created_at": run.created_at,
            "sources": [],
            "parent_user_message_id": run.user_message_id,
            "versions": [],
        }
        messages.append(answer)
    answer["pending_run_id"] = run.id
    answer["versions"].append(
        {
            "run_id": run.id,
            "status": "pending",
            "created_at": run.created_at,
        }
    )


def answer_snapshot(answer: dict[str, Any], run: Run) -> None:
    answer.update(
        content=run.answer,
        status=run.status,
        run_id=run.id,
        sources=run.sources,
        answer_status=run.answer_status,
    )


def finish_answer(session: dict[str, Any], run: Run, finished: str) -> dict[str, Any]:
    messages = normalize_messages(session["messages"])
    answer = next(
        (
            m
            for m in messages
            if m["role"] == "assistant"
            and (m["id"] == run.assistant_message_id or m.get("pending_run_id") == run.id)
        ),
        None,
    )
    if answer is None:  # Recover runs accepted before logical answer placeholders existed.
        run.assistant_message_id = uuid4().hex
        run.user_message_id = next((m["id"] for m in messages if m.get("run_id") == run.id), None)
        answer = {
            "id": run.assistant_message_id,
            "role": "assistant",
            "created_at": finished,
            "parent_user_message_id": run.user_message_id,
            "versions": [],
        }
        messages.append(answer)
    versions = answer["versions"]
    version = next((v for v in versions if v["run_id"] == run.id), None)
    if version is None:
        version = {"run_id": run.id, "created_at": run.created_at or finished}
        versions.append(version)
    version["status"] = run.status
    if run.status == "completed" or answer.get("status") != "completed":
        answer_snapshot(answer, run)
    answer.pop("pending_run_id", None)
    return answer


def choose_version(
    session: dict[str, Any], message_id: str, run: Run, expected: str
) -> dict[str, Any]:
    if session.get("active_run_id"):
        raise ConflictError("Wait for the current response to finish")
    answer = latest_answer(session, message_id)
    if answer.get("run_id") != expected:
        raise ConflictError("The selected answer changed. Refresh this conversation and retry.")
    if run.status != "completed" or not any(v["run_id"] == run.id for v in answer["versions"]):
        raise ConflictError("Choose a completed version of this reply")
    answer_snapshot(answer, run)
    return answer


def context_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages = normalize_messages(messages)
    users = {m["id"]: m for m in messages if m["role"] == "user"}
    selected = []
    for answer in messages:
        if (
            answer["role"] != "assistant"
            or answer.get("status") != "completed"
            or answer.get("pending_run_id")
            or answer.get("answer_status", "answered") not in {"answered", "clarification"}
            or answer["content"].startswith(
                "I cannot verify an answer from the available authorized sources."
            )
        ):
            continue
        if user := users.get(answer.get("parent_user_message_id")):
            selected.extend([user, answer])
    return selected
