"""Authenticated OpenWebUI API client for audit-assistant integrations."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from auditor_support_tool.services.openwebui_settings_service import (
    normalize_openwebui_url,
)


class OpenWebUIClientError(RuntimeError):
    """Raised when an authenticated OpenWebUI API operation fails."""


@dataclass(frozen=True, slots=True)
class OpenWebUIModel:
    """One model available to the current OpenWebUI account."""

    model_id: str
    name: str


@dataclass(frozen=True, slots=True)
class OpenWebUIConnectionResult:
    """Outcome of an authenticated OpenWebUI connectivity check."""

    success: bool
    message: str
    model_count: int = 0
    models: tuple[OpenWebUIModel, ...] = ()


@dataclass(frozen=True, slots=True)
class OpenWebUIAnalysisResult:
    """Persistent OpenWebUI analysis created from an audit report."""

    chat_id: str
    chat_url: str
    model: str
    uploaded_file_id: str


class OpenWebUIClient:
    """Call the OpenWebUI API surface required by the Auditor Support Tool."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OpenWebUI timeout must be greater than zero.")

        self._timeout_seconds = timeout_seconds

    def list_models(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> tuple[OpenWebUIModel, ...]:
        """Return models available to the authenticated user."""

        payload = self._request_json(
            method="GET",
            url=(f"{normalize_openwebui_url(base_url)}/api/models"),
            api_key=api_key,
        )

        raw_models = payload.get(
            "data",
            [],
        )

        if not isinstance(raw_models, list):
            return ()

        models: list[OpenWebUIModel] = []

        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue

            model_id = str(raw_model.get("id", "")).strip()

            if not model_id:
                continue

            model_name = str(raw_model.get("name") or raw_model.get("model") or model_id).strip()

            models.append(
                OpenWebUIModel(
                    model_id=model_id,
                    name=model_name,
                )
            )

        return tuple(models)

    def test_connection(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> OpenWebUIConnectionResult:
        """Authenticate and retrieve the user's available model list."""

        cleaned_key = api_key.strip()

        if not cleaned_key:
            return OpenWebUIConnectionResult(
                success=False,
                message=("No OpenWebUI API key is configured for this address."),
            )

        try:
            models = self.list_models(
                base_url=base_url,
                api_key=cleaned_key,
            )
        except OpenWebUIClientError as error:
            return OpenWebUIConnectionResult(
                success=False,
                message=str(error),
            )

        return OpenWebUIConnectionResult(
            success=True,
            message=(
                "Connected to OpenWebUI successfully. "
                f"{len(models)} model(s) are available to this account."
            ),
            model_count=len(models),
            models=models,
        )

    def analyse_audit_report(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        title: str,
        filename: str,
        content: bytes,
        prompt: str,
    ) -> OpenWebUIAnalysisResult:
        """Upload a report and create a persistent OpenWebUI analysis chat."""

        normalized_url = normalize_openwebui_url(base_url)
        cleaned_model = model.strip()
        cleaned_title = title.strip()

        if not cleaned_model:
            raise OpenWebUIClientError("An OpenWebUI model is required for audit-report analysis.")

        if not cleaned_title:
            raise OpenWebUIClientError("An OpenWebUI chat title is required.")

        file_id = self._upload_file(
            base_url=normalized_url,
            api_key=api_key,
            filename=filename,
            content=content,
            content_type="application/json",
        )

        user_message_id = str(uuid.uuid4())
        assistant_message_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        timestamp = int(time.time())

        file_reference = {
            "id": file_id,
            "type": "file",
            "status": "processed",
        }

        user_message = {
            "id": user_message_id,
            "role": "user",
            "content": prompt,
            "timestamp": timestamp,
            "models": [cleaned_model],
            "childrenIds": [assistant_message_id],
        }
        assistant_message = {
            "id": assistant_message_id,
            "role": "assistant",
            "content": "",
            "parentId": user_message_id,
            "childrenIds": [],
            "model": cleaned_model,
            "modelName": cleaned_model,
            "modelIdx": 0,
            "done": False,
            "timestamp": timestamp + 1,
        }

        chat_payload = {
            "chat": {
                "title": cleaned_title,
                "models": [cleaned_model],
                "messages": [
                    user_message,
                    assistant_message,
                ],
                "history": {
                    "currentId": assistant_message_id,
                    "messages": {
                        user_message_id: user_message,
                        assistant_message_id: assistant_message,
                    },
                },
                "currentId": assistant_message_id,
                "files": [file_reference],
                "params": {},
                "tags": [],
                "timestamp": int(time.time() * 1000),
            }
        }

        created_chat = self._request_json(
            method="POST",
            url=f"{normalized_url}/api/v1/chats/new",
            api_key=api_key,
            payload=chat_payload,
        )

        chat_id = str(created_chat.get("id", "")).strip()

        if not chat_id:
            raise OpenWebUIClientError(
                "OpenWebUI created the analysis request but did not return "
                "a persistent chat identifier."
            )

        completion_payload = {
            "chat_id": chat_id,
            "id": assistant_message_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "model": cleaned_model,
            "stream": False,
            "files": [file_reference],
            "background_tasks": {
                "title_generation": False,
                "tags_generation": False,
                "follow_up_generation": False,
            },
            "features": {
                "code_interpreter": False,
                "web_search": False,
                "image_generation": False,
                "memory": False,
            },
            "session_id": session_id,
        }

        self._request_json(
            method="POST",
            url=f"{normalized_url}/api/chat/completions",
            api_key=api_key,
            payload=completion_payload,
        )

        return OpenWebUIAnalysisResult(
            chat_id=chat_id,
            chat_url=f"{normalized_url}/c/{chat_id}",
            model=cleaned_model,
            uploaded_file_id=file_id,
        )

    def _upload_file(
        self,
        *,
        base_url: str,
        api_key: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """Upload one report file and wait for synchronous processing."""

        boundary = f"----AuditorSupportTool{uuid.uuid4().hex}"
        body = self._multipart_body(
            boundary=boundary,
            filename=filename,
            content=content,
            content_type=content_type,
        )

        query = urlencode(
            {
                "process": "true",
                "process_in_background": "false",
            }
        )

        payload = self._request_json(
            method="POST",
            url=(f"{base_url}/api/v1/files/?{query}"),
            api_key=api_key,
            raw_body=body,
            content_type=(f"multipart/form-data; boundary={boundary}"),
        )

        file_id = str(payload.get("id", "")).strip()

        if not file_id:
            raise OpenWebUIClientError(
                "OpenWebUI did not return a file identifier for the uploaded audit report."
            )

        return file_id

    @staticmethod
    def _multipart_body(
        *,
        boundary: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> bytes:
        safe_filename = filename.replace('"', "_").replace("\r", "_").replace("\n", "_")

        prefix = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; '
            f'filename="{safe_filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()

        suffix = (f"\r\n--{boundary}--\r\n").encode()

        return prefix + content + suffix

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        api_key: str,
        payload: dict[str, object] | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
    ) -> dict[str, object]:
        """Perform one authenticated request and return a JSON object."""

        cleaned_key = api_key.strip()

        if not cleaned_key:
            raise OpenWebUIClientError("No OpenWebUI API key is configured for this address.")

        if payload is not None and raw_body is not None:
            raise ValueError("Use either a JSON payload or raw request body, not both.")

        body = raw_body

        if payload is not None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")

        headers = {
            "Accept": "application/json",
            "Authorization": (f"Bearer {cleaned_key}"),
        }

        if body is not None:
            headers["Content-Type"] = content_type

        request = Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_body = response.read()
        except HTTPError as error:
            if error.code in {
                401,
                403,
            }:
                raise OpenWebUIClientError(
                    "OpenWebUI rejected the API key or the current account "
                    "does not have permission for this operation."
                ) from error

            detail = ""

            try:
                detail = error.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except OSError:
                pass

            message = f"OpenWebUI returned HTTP {error.code}."

            if detail.strip():
                message += f" Server response: {detail.strip()[:500]}"

            raise OpenWebUIClientError(message) from error
        except (
            URLError,
            TimeoutError,
        ) as error:
            raise OpenWebUIClientError(
                "OpenWebUI could not be reached. Check the configured "
                f"address, network or VPN connection. Details: {error}"
            ) from error

        if not response_body:
            return {}

        try:
            decoded = json.loads(response_body.decode("utf-8"))
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise OpenWebUIClientError(
                "OpenWebUI responded, but the response could not be interpreted as JSON."
            ) from error

        if not isinstance(decoded, dict):
            raise OpenWebUIClientError("OpenWebUI returned an unexpected response structure.")

        return decoded
