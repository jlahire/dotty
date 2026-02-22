"""
dotty v2 — email parser
by jLaHire

PST/OST via pypff, MBOX via mailbox, EML via email stdlib.
"""

from __future__ import annotations

import email
import email.utils
import logging
import mailbox
import re
from pathlib import Path

from graph import Node, make_id

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+")


def analyze_email(root_path: str) -> list[Node]:
    root = Path(root_path)
    nodes = []

    for pst in root.rglob("*.pst"):
        nodes.extend(_parse_pst(pst))
    for ost in root.rglob("*.ost"):
        nodes.extend(_parse_pst(ost))
    for mbox in root.rglob("*.mbox"):
        nodes.extend(_parse_mbox(mbox))
    for eml in root.rglob("*.eml"):
        nodes.extend(_parse_eml(eml))

    return nodes


def _parse_pst(pst_path: Path) -> list[Node]:
    try:
        import pypff
    except ImportError:
        log.debug("pypff not installed")
        return []

    nodes = []
    try:
        pst = pypff.file()
        pst.open(str(pst_path))
        root = pst.get_root_folder()
        _walk_pst_folder(root, pst_path, nodes)
        pst.close()
    except Exception as e:
        log.debug(f"pst: {e}")
    return nodes


def _walk_pst_folder(folder, source_path, nodes):
    for i in range(folder.get_number_of_sub_messages()):
        try:
            msg = folder.get_sub_message(i)
            _pst_message(msg, source_path, nodes)
        except Exception:
            continue

    for i in range(folder.get_number_of_sub_folders()):
        try:
            sub = folder.get_sub_folder(i)
            _walk_pst_folder(sub, source_path, nodes)
        except Exception:
            continue


def _pst_message(msg, source_path, nodes):
    subject = ""
    sender = ""
    date_str = ""

    try:
        subject = msg.get_subject() or ""
    except Exception:
        pass
    try:
        sender = msg.get_sender_name() or ""
        sender_email = msg.get_sender_email_address() or ""
        if sender_email and sender_email not in sender:
            sender = f"{sender} <{sender_email}>"
    except Exception:
        pass
    try:
        dt = msg.get_delivery_time()
        if dt:
            date_str = dt.isoformat()
    except Exception:
        pass

    recipients = []
    try:
        for i in range(msg.get_number_of_recipients()):
            r = msg.get_recipient(i)
            recipients.append(str(r))
    except Exception:
        pass

    body_preview = ""
    try:
        body = msg.get_plain_text_body()
        if body:
            body_preview = body.decode("utf-8", errors="ignore")[:200]
    except Exception:
        pass

    node_id = make_id(f"email:{source_path}:{subject}:{date_str}")
    nodes.append(Node(
        id=node_id,
        name=subject or "(no subject)",
        path=str(source_path),
        kind="email",
        info={
            "subject": subject, "sender": sender,
            "recipients": recipients, "date": date_str,
            "preview": body_preview, "source": str(source_path),
        },
    ))

    try:
        for i in range(msg.get_number_of_attachments()):
            att = msg.get_attachment(i)
            att_name = str(att.get_name() or f"attachment_{i}")
            nodes.append(Node(
                id=make_id(f"att:{node_id}:{att_name}"),
                name=att_name,
                path=f"{source_path}/{att_name}",
                kind="email_attachment",
                info={
                    "parent_email": node_id,
                    "size": att.get_size() if hasattr(att, "get_size") else 0,
                    "extension": Path(att_name).suffix.lower(),
                },
            ))
    except Exception:
        pass


def _parse_mbox(mbox_path: Path) -> list[Node]:
    nodes = []
    try:
        mbox = mailbox.mbox(str(mbox_path))
        for idx, msg in enumerate(mbox):
            _stdlib_message(msg, mbox_path, nodes)
            if idx >= 5000:
                break
    except Exception as e:
        log.debug(f"mbox: {e}")
    return nodes


def _parse_eml(eml_path: Path) -> list[Node]:
    nodes = []
    try:
        with open(eml_path, "rb") as f:
            msg = email.message_from_binary_file(f)
        _stdlib_message(msg, eml_path, nodes)
    except Exception as e:
        log.debug(f"eml: {e}")
    return nodes


def _stdlib_message(msg, source_path, nodes):
    subject = msg.get("Subject", "")
    sender = msg.get("From", "")
    to = msg.get("To", "")
    date_str = ""

    try:
        dt = email.utils.parsedate_to_datetime(msg.get("Date", ""))
        date_str = dt.isoformat()
    except Exception:
        pass

    body_preview = ""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == "attachment":
                attachments.append(part.get_filename() or "attachment")
            elif ct in ("text/plain", "text/html") and not body_preview:
                payload = part.get_payload(decode=True)
                if payload:
                    body_preview = payload.decode("utf-8", errors="ignore")[:200]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_preview = payload.decode("utf-8", errors="ignore")[:200]

    node_id = make_id(f"email:{source_path}:{subject}:{date_str}")
    nodes.append(Node(
        id=node_id,
        name=subject or "(no subject)",
        path=str(source_path),
        kind="email",
        info={
            "subject": subject, "sender": sender, "to": to,
            "date": date_str, "preview": body_preview,
            "source": str(source_path),
        },
    ))

    for att_name in attachments:
        nodes.append(Node(
            id=make_id(f"att:{node_id}:{att_name}"),
            name=att_name,
            path=f"{source_path}/{att_name}",
            kind="email_attachment",
            info={
                "parent_email": node_id,
                "extension": Path(att_name).suffix.lower(),
            },
        ))
