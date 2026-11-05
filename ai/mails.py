"""Read incoming mails from the inbox folder: one .eml or .txt file per mail."""
import email
import email.policy
import email.utils
from dataclasses import dataclass
from pathlib import Path

# Header names accepted in a .txt mail, Dutch or English, mapped to the field they fill.
TXT_HEADERS = {
    "van": "sender",
    "from": "sender",
    "onderwerp": "subject",
    "subject": "subject",
    "datum": "date",
    "date": "date",
    "message-id": "message_id",
}


@dataclass
class Mail:
    path: Path
    sender_name: str
    sender_email: str
    subject: str
    date: str
    message_id: str
    body: str

    @property
    def reference(self):
        """Stable key to recognise a mail that was already processed (no <>: they get escaped in HTML)."""
        return self.message_id.strip("<>") or self.path.name


def read_inbox(folder):
    """All mails in the folder, sorted by file name."""
    folder = Path(folder)
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".eml", ".txt"))
    return [read_mail(path) for path in paths]


def read_mail(path):
    path = Path(path)
    if path.suffix.lower() == ".eml":
        return _read_eml(path)
    return _read_txt(path)


def _read_eml(path):
    message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    name, address = email.utils.parseaddr(str(message.get("From", "")))
    part = message.get_body(preferencelist=("plain",))
    body = part.get_content() if part else ""
    return Mail(
        path=path,
        sender_name=name,
        sender_email=address.lower(),
        subject=str(message.get("Subject", "")),
        date=str(message.get("Date", "")),
        message_id=str(message.get("Message-ID", "")).strip(),
        body=body.strip(),
    )


def _read_txt(path):
    """Plain text: optional 'Header: value' lines, a blank line, then the body."""
    lines = path.read_text(encoding="utf-8").splitlines()
    fields = {}
    index = 0
    for index, line in enumerate(lines):
        if not line.strip():
            break
        key, sep, value = line.partition(":")
        if not sep or key.strip().lower() not in TXT_HEADERS:
            index -= 1  # no header block: the whole file is the body
            break
        fields[TXT_HEADERS[key.strip().lower()]] = value.strip()
    body = "\n".join(lines[index + 1:]).strip()
    name, address = email.utils.parseaddr(fields.get("sender", ""))
    return Mail(
        path=path,
        sender_name=name,
        sender_email=address.lower(),
        subject=fields.get("subject", ""),
        date=fields.get("date", ""),
        message_id=fields.get("message_id", ""),
        body=body,
    )
