"""
dotty v2 — web security analysis
by jLaHire

passive security scanner: header auditing (drheader), cookie parsing,
form inspection, mixed content detection, SRI checks, info disclosure.
produces web_finding and web_cookie nodes for the graph.
"""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie

from graph import Node, make_id

log = logging.getLogger(__name__)

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "pass": 3}


def analyze_web_security(graph) -> list[Node]:
    nodes = list(graph.nodes.values())
    page_node = next((n for n in nodes if n.kind == "web_page"), None)
    if not page_node:
        return []

    headers_node = next((n for n in nodes if n.kind == "web_headers"), None)
    form_nodes = [n for n in nodes if n.kind == "web_form"]
    input_nodes = [n for n in nodes if n.kind == "web_input"]
    script_nodes = [n for n in nodes if n.kind == "web_script" and not n.info.get("inline")]
    inline_node = next((n for n in nodes if n.kind == "web_script" and n.info.get("inline")), None)

    findings = []

    findings += _check_headers_drheader(headers_node)
    findings += _check_cookies(page_node)
    findings += _check_session_cookies(nodes, page_node)
    findings += _check_forms(form_nodes, input_nodes, page_node.info.get("scheme", "https"))
    findings += _check_mixed_content(page_node, [n for n in nodes if n.kind in ("web_script", "web_style", "web_image", "web_iframe")])
    findings += _check_scripts(script_nodes, inline_node)
    findings += _check_information_disclosure(page_node)

    # summary
    total = len(findings)
    if total:
        counts = {"critical": 0, "warning": 0, "info": 0, "pass": 0}
        for f in findings:
            sev = f.info.get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
        pass_count = counts["pass"]
        score = round((pass_count / total) * 100) if total else 100
        findings.append(Node(
            id=make_id("websec:summary"),
            name=f"Security Score: {score}/100",
            path="#security-summary",
            kind="web_finding",
            info={
                "category": "summary",
                "severity": "info",
                "score": score,
                "total": total,
                "critical": counts["critical"],
                "warning": counts["warning"],
                "info": counts["info"],
                "pass": counts["pass"],
            },
        ))

    return findings


# --- header audit ---

def _check_headers_drheader(headers_node) -> list[Node]:
    if not headers_node:
        return []

    headers_dict = dict(headers_node.info)
    findings = []

    try:
        from drheader import Drheader
        scanner = Drheader(headers=headers_dict)
        results = scanner.analyze()
    except ImportError:
        log.info("drheader not installed, using basic header checks")
        return _basic_header_checks(headers_dict)
    except Exception as e:
        log.warning(f"drheader failed ({e}), falling back to basic checks")
        return _basic_header_checks(headers_dict)

    severity_map = {
        "high": "critical",
        "medium": "warning",
        "low": "info",
    }

    for r in results:
        rule = r.get("rule", "Unknown")
        sev = severity_map.get(r.get("severity", "").lower(), "warning")
        msg = r.get("message", "")
        value = r.get("value", "")
        expected = r.get("expected", "")

        findings.append(Node(
            id=make_id(f"websec:header:{rule}"),
            name=f"{rule}",
            path=f"#security:header:{rule}",
            kind="web_finding",
            info={
                "category": "headers",
                "severity": sev,
                "title": rule,
                "detail": msg,
                "value": str(value)[:200],
                "expected": str(expected)[:200],
            },
        ))

    # add pass nodes for headers that drheader didn't flag
    checked_rules = {r.get("rule", "").lower() for r in results}
    important_headers = {
        "content-security-policy": "Content-Security-Policy",
        "strict-transport-security": "Strict-Transport-Security",
        "x-frame-options": "X-Frame-Options",
        "x-content-type-options": "X-Content-Type-Options",
        "referrer-policy": "Referrer-Policy",
    }
    headers_lower = {k.lower(): v for k, v in headers_dict.items()}
    for key, label in important_headers.items():
        if key not in checked_rules and key in headers_lower:
            findings.append(Node(
                id=make_id(f"websec:header:pass:{key}"),
                name=f"{label} present",
                path=f"#security:header:pass:{key}",
                kind="web_finding",
                info={
                    "category": "headers",
                    "severity": "pass",
                    "title": f"{label} present",
                    "detail": f"Header is set: {headers_lower[key][:100]}",
                },
            ))

    return findings


def _basic_header_checks(headers_dict: dict) -> list[Node]:
    findings = []
    h = {k.lower(): v for k, v in headers_dict.items()}

    checks = [
        ("content-security-policy", "Content-Security-Policy", "critical",
         "No Content-Security-Policy header — XSS risk"),
        ("strict-transport-security", "Strict-Transport-Security", "warning",
         "No HSTS header — downgrade attack risk"),
        ("x-frame-options", "X-Frame-Options", "warning",
         "No X-Frame-Options — clickjacking risk"),
        ("x-content-type-options", "X-Content-Type-Options", "warning",
         "No X-Content-Type-Options — MIME sniffing risk"),
        ("referrer-policy", "Referrer-Policy", "info",
         "No Referrer-Policy header"),
    ]

    for key, label, severity, message in checks:
        if key in h:
            findings.append(Node(
                id=make_id(f"websec:header:pass:{key}"),
                name=f"{label} present",
                path=f"#security:header:pass:{key}",
                kind="web_finding",
                info={
                    "category": "headers",
                    "severity": "pass",
                    "title": f"{label} present",
                    "detail": f"Header is set: {h[key][:100]}",
                },
            ))
        else:
            findings.append(Node(
                id=make_id(f"websec:header:missing:{key}"),
                name=f"Missing {label}",
                path=f"#security:header:missing:{key}",
                kind="web_finding",
                info={
                    "category": "headers",
                    "severity": severity,
                    "title": f"Missing {label}",
                    "detail": message,
                },
            ))

    return findings


# --- cookies ---

def _check_cookies(page_node) -> list[Node]:
    set_cookie = page_node.info.get("set_cookie", "")
    if not set_cookie:
        return []

    findings = []
    is_https = page_node.info.get("is_https", True)

    sc = SimpleCookie()
    try:
        sc.load(set_cookie)
    except Exception:
        return []

    for name, morsel in sc.items():
        secure = morsel.get("secure", "") != ""
        httponly = morsel.get("httponly", "") != ""
        samesite = morsel.get("samesite", "")
        domain = morsel.get("domain", "")
        path = morsel.get("path", "")
        expires = morsel.get("expires", "")

        cookie_node = Node(
            id=make_id(f"webcookie:{name}"),
            name=name,
            path=f"#cookie:{name}",
            kind="web_cookie",
            info={
                "name": name,
                "value": morsel.coded_value[:20] + "..." if len(morsel.coded_value) > 20 else morsel.coded_value,
                "secure": secure,
                "httponly": httponly,
                "samesite": samesite,
                "domain": domain,
                "path": path,
                "expires": expires,
            },
        )
        findings.append(cookie_node)

        if is_https and not secure:
            findings.append(Node(
                id=make_id(f"websec:cookie:nosecure:{name}"),
                name=f"Cookie '{name}' missing Secure flag",
                path=f"#security:cookie:nosecure:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "warning",
                    "title": f"Cookie '{name}' without Secure flag",
                    "detail": "HTTPS page sets cookie without Secure attribute — cookie sent over HTTP too",
                },
            ))

        if not httponly:
            findings.append(Node(
                id=make_id(f"websec:cookie:nohttponly:{name}"),
                name=f"Cookie '{name}' missing HttpOnly",
                path=f"#security:cookie:nohttponly:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "warning",
                    "title": f"Cookie '{name}' without HttpOnly",
                    "detail": "Cookie accessible via JavaScript — XSS can steal it",
                },
            ))

        if not samesite:
            findings.append(Node(
                id=make_id(f"websec:cookie:nosamesite:{name}"),
                name=f"Cookie '{name}' missing SameSite",
                path=f"#security:cookie:nosamesite:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "info",
                    "title": f"Cookie '{name}' without SameSite",
                    "detail": "No SameSite attribute — browser defaults apply",
                },
            ))

    return findings


# --- forms ---

def _check_forms(form_nodes, input_nodes, page_scheme) -> list[Node]:
    findings = []
    is_https = page_scheme == "https"

    for form_node in form_nodes:
        action = form_node.info.get("action", "")
        form_idx = -1
        # find matching form index by checking the form node's name pattern
        for idx, inp in enumerate(input_nodes):
            if inp.info.get("form_name") and inp.info.get("form_name") == form_node.name:
                form_idx = inp.info.get("form_index", -1)
                break

        # form action over HTTP on HTTPS page
        if is_https and action.startswith("http://"):
            findings.append(Node(
                id=make_id(f"websec:form:http:{action}"),
                name=f"Form submits to HTTP",
                path=f"#security:form:http:{form_node.name}",
                kind="web_finding",
                info={
                    "category": "forms",
                    "severity": "critical",
                    "title": f"Form '{form_node.name}' submits over HTTP",
                    "detail": f"HTTPS page sends form data to insecure endpoint: {action}",
                },
            ))

        # check for password fields and CSRF tokens
        form_inputs = [n for n in input_nodes if n.info.get("form_name") == form_node.name]
        has_password = any(n.info.get("type", "").lower() == "password" for n in form_inputs)
        csrf_names = {"csrf", "csrfmiddlewaretoken", "_token", "csrf_token",
                      "authenticity_token", "__requestverificationtoken", "_csrf"}
        has_csrf = any(
            n.info.get("hidden") and n.info.get("name", "").lower() in csrf_names
            for n in form_inputs
        )

        if has_password and not has_csrf:
            findings.append(Node(
                id=make_id(f"websec:form:nocsrf:{form_node.name}"),
                name=f"Password form without CSRF token",
                path=f"#security:form:nocsrf:{form_node.name}",
                kind="web_finding",
                info={
                    "category": "forms",
                    "severity": "warning",
                    "title": f"Password field in '{form_node.name}' without visible CSRF token",
                    "detail": "Form has password input but no hidden CSRF token field detected",
                },
            ))

        # file upload
        has_file = any(n.info.get("type", "").lower() == "file" for n in form_inputs)
        if has_file:
            findings.append(Node(
                id=make_id(f"websec:form:upload:{form_node.name}"),
                name=f"File upload in '{form_node.name}'",
                path=f"#security:form:upload:{form_node.name}",
                kind="web_finding",
                info={
                    "category": "forms",
                    "severity": "info",
                    "title": f"File upload in '{form_node.name}'",
                    "detail": "Form accepts file uploads",
                },
            ))

        # hidden fields
        hidden_inputs = [n for n in form_inputs if n.info.get("hidden")]
        if hidden_inputs:
            names = ", ".join(n.info.get("name", "?") for n in hidden_inputs[:10])
            findings.append(Node(
                id=make_id(f"websec:form:hidden:{form_node.name}"),
                name=f"Hidden fields in '{form_node.name}'",
                path=f"#security:form:hidden:{form_node.name}",
                kind="web_finding",
                info={
                    "category": "forms",
                    "severity": "info",
                    "title": f"Hidden fields in '{form_node.name}'",
                    "detail": f"{len(hidden_inputs)} hidden input(s): {names}",
                },
            ))

    return findings


# --- mixed content ---

def _check_mixed_content(page_node, resource_nodes) -> list[Node]:
    if not page_node.info.get("is_https"):
        return []

    findings = []

    for node in resource_nodes:
        url = node.info.get("url", node.path)
        if not url.startswith("http://"):
            continue

        is_active = node.kind in ("web_script", "web_iframe")
        sev = "critical" if is_active else "warning"
        label = "active" if is_active else "passive"

        findings.append(Node(
            id=make_id(f"websec:mixed:{url}"),
            name=f"Mixed content ({label}): {node.name}",
            path=f"#security:mixed:{node.name}",
            kind="web_finding",
            info={
                "category": "mixed_content",
                "severity": sev,
                "title": f"Mixed {label} content: {node.name}",
                "detail": f"{node.kind} loaded over HTTP on HTTPS page: {url}",
            },
        ))

    return findings


# --- scripts / SRI ---

def _check_scripts(script_nodes, inline_node) -> list[Node]:
    findings = []

    for node in script_nodes:
        if node.info.get("third_party") and not node.info.get("integrity"):
            findings.append(Node(
                id=make_id(f"websec:sri:{node.info.get('url', '')}"),
                name=f"No SRI: {node.name}",
                path=f"#security:sri:{node.name}",
                kind="web_finding",
                info={
                    "category": "scripts",
                    "severity": "warning",
                    "title": f"Third-party script without SRI: {node.name}",
                    "detail": f"Script from {node.info.get('domain', '?')} loaded without integrity attribute",
                },
            ))

    if inline_node:
        dangerous = []
        if inline_node.info.get("has_eval"):
            dangerous.append("eval()")
        if inline_node.info.get("has_document_write"):
            dangerous.append("document.write()")

        if dangerous:
            findings.append(Node(
                id=make_id("websec:inline:dangerous"),
                name=f"Dangerous JS patterns",
                path="#security:inline:dangerous",
                kind="web_finding",
                info={
                    "category": "scripts",
                    "severity": "warning",
                    "title": "Dangerous JavaScript patterns in inline scripts",
                    "detail": f"Found: {', '.join(dangerous)}",
                },
            ))

        storage = []
        if inline_node.info.get("has_localstorage"):
            storage.append("localStorage")
        if inline_node.info.get("has_sessionstorage"):
            storage.append("sessionStorage")
        if inline_node.info.get("has_indexeddb"):
            storage.append("indexedDB")

        if storage:
            findings.append(Node(
                id=make_id("websec:inline:storage"),
                name=f"Client storage usage",
                path="#security:inline:storage",
                kind="web_finding",
                info={
                    "category": "scripts",
                    "severity": "info",
                    "title": "Client-side storage API usage",
                    "detail": f"Inline scripts reference: {', '.join(storage)}",
                },
            ))

    return findings


# --- information disclosure ---

def _check_information_disclosure(page_node) -> list[Node]:
    findings = []
    server = page_node.info.get("server", "")
    x_powered = page_node.info.get("x_powered_by", "")

    if server and any(c.isdigit() for c in server):
        findings.append(Node(
            id=make_id("websec:info:server"),
            name="Server version disclosed",
            path="#security:info:server",
            kind="web_finding",
            info={
                "category": "information_disclosure",
                "severity": "info",
                "title": "Server header reveals version",
                "detail": f"Server: {server}",
            },
        ))

    if x_powered:
        findings.append(Node(
            id=make_id("websec:info:xpowered"),
            name="X-Powered-By disclosed",
            path="#security:info:xpowered",
            kind="web_finding",
            info={
                "category": "information_disclosure",
                "severity": "info",
                "title": "X-Powered-By header present",
                "detail": f"X-Powered-By: {x_powered}",
            },
        ))

    return findings


# --- session cookies (interactive mode) ---

def _check_session_cookies(nodes, page_node) -> list[Node]:
    cookie_nodes = [n for n in nodes if n.kind == "web_cookie" and n.info.get("interactive")]
    if not cookie_nodes:
        return []

    findings = []
    is_https = page_node.info.get("is_https", True)

    for cn in cookie_nodes:
        name = cn.info.get("name", cn.name)
        secure = cn.info.get("secure", False)
        httponly = cn.info.get("httponly", False)
        samesite = cn.info.get("samesite", "")

        if is_https and not secure:
            findings.append(Node(
                id=make_id(f"session:cookie:nosecure:{name}"),
                name=f"Session cookie '{name}' missing Secure flag",
                path=f"#security:session:cookie:nosecure:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "warning",
                    "title": f"Session cookie '{name}' without Secure flag",
                    "detail": "HTTPS session sets cookie without Secure attribute",
                },
            ))

        if not httponly:
            findings.append(Node(
                id=make_id(f"session:cookie:nohttponly:{name}"),
                name=f"Session cookie '{name}' missing HttpOnly",
                path=f"#security:session:cookie:nohttponly:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "warning",
                    "title": f"Session cookie '{name}' without HttpOnly",
                    "detail": "Cookie accessible via JavaScript — XSS can steal it",
                },
            ))

        if not samesite:
            findings.append(Node(
                id=make_id(f"session:cookie:nosamesite:{name}"),
                name=f"Session cookie '{name}' missing SameSite",
                path=f"#security:session:cookie:nosamesite:{name}",
                kind="web_finding",
                info={
                    "category": "cookies",
                    "severity": "info",
                    "title": f"Session cookie '{name}' without SameSite",
                    "detail": "No SameSite attribute — browser defaults apply",
                },
            ))

    return findings
