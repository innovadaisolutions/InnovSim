"""Bounded, read-only email-to-fixture import. No mailbox credentials or fetches."""

from __future__ import annotations

import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from html.parser import HTMLParser
from typing import ClassVar
from uuid import uuid4

from pydantic import Field, field_validator

from .fixtures import supplier_delay
from .models import Scenario, StrictModel

MAX_EMAIL_BYTES = 131_072


class EmailImport(StrictModel):
    text: str = Field(min_length=1, max_length=MAX_EMAIL_BYTES)
    name: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("text")
    @classmethod
    def bounded_utf8(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_EMAIL_BYTES:
            raise ValueError("Email input must not exceed 128 KiB of UTF-8 text.")
        return value


class _TextOnlyHTML(HTMLParser):
    BLOCKS: ClassVar[set[str]] = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "blockquote"}
    HIDDEN: ClassVar[set[str]] = {"script", "style", "iframe", "object", "svg", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.HIDDEN:
            self.hidden.append(tag)
        elif tag in self.BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.hidden:
            index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
            self.hidden = self.hidden[:index]
        elif tag in self.BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _clean_text(text: str, *, html: bool = False) -> str:
    if html or re.search(
        r"<(?:html|body|script|style|iframe|div|p|br)\b", text, flags=re.IGNORECASE
    ):
        parser = _TextOnlyHTML()
        parser.feed(text)
        parser.close()
        text = "".join(parser.parts)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(character for character in text if character in "\n\t" or ord(character) >= 32)
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def _extract_body(message: EmailMessage, counts: list[int], depth: int = 0) -> str:
    counts[0] += 1
    if counts[0] > 100 or depth > 10:
        raise ValueError("Email MIME structure exceeds the 100-part or 10-level import limit.")
    if message.get_content_disposition() == "attachment" or message.get_filename():
        return ""
    if message.get_content_maintype() == "message":
        # Forwarded RFC822 parts may be attachments; they are not the message body.
        return ""
    if message.is_multipart():
        children = list(message.iter_parts())
        if message.get_content_subtype() == "alternative":
            plain = [child for child in children if child.get_content_type() == "text/plain"]
            other = [child for child in children if child not in plain]
            # Prefer plain text without leaking a duplicate HTML alternative.
            for child in plain + other:
                body = _extract_body(child, counts, depth + 1)
                if body:
                    return body
            return ""
        return "\n\n".join(
            body for child in children if (body := _extract_body(child, counts, depth + 1))
        )
    content_type = message.get_content_type()
    if content_type not in {"text/plain", "text/html"}:
        return ""
    try:
        content = message.get_content()
    except (LookupError, UnicodeError):
        payload = message.get_payload(decode=True) or b""
        content = payload.decode("utf-8", errors="replace")
    return _clean_text(str(content), html=content_type == "text/html")


def import_email(request: EmailImport) -> Scenario:
    """Preserve source body as context, while explicitly retaining synthetic world facts."""
    raw = request.text.encode("utf-8")
    if len(raw) > MAX_EMAIL_BYTES:
        raise ValueError("Email input must not exceed 128 KiB.")
    subject = ""
    header = request.text.split("\n\n", 1)[0]
    is_rfc822 = bool(re.search(r"(?im)^(?:from|to|subject|mime-version|content-type):", header))
    if is_rfc822:
        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
            for count, _ in enumerate(message.walk(), start=1):
                if count > 100:
                    raise ValueError("Email MIME structure exceeds the 100-part import limit.")
        except RecursionError as error:
            raise ValueError("Email MIME nesting exceeds the import limit.") from error
        body = _extract_body(message, [0])
        subject = _clean_text(str(message.get("subject", "")))
    else:
        body = _clean_text(request.text)
    if not body:
        raise ValueError("The imported email contains no usable plain text or HTML body.")
    if len(body.encode("utf-8")) > MAX_EMAIL_BYTES:
        raise ValueError("Decoded email body must not exceed 128 KiB.")
    scenario = supplier_delay()
    scenario.id = f"email-{uuid4().hex}"
    scenario.name = request.name or subject[:160] or "Imported email fixture"
    scenario.initial_message = body
    scenario.description = (
        "Imported local email body used as fixture context. Attachments and active HTML content were discarded. "
        "Stock, quantities, delivery times, budgets and companies remain synthetic supplier-delay example values. "
        "Import does not reconstruct real business truth, fetch a mailbox, contact clients or send messages."
    )
    return Scenario.model_validate(scenario.model_dump())
