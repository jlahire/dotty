"""
dotty v2 — ollama chat service
by jLaHire

builds context from the graph, greps files, reads web content,
surfaces tagged/favorited nodes. streams responses.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a forensic analysis assistant inside Dotty, a filesystem and web "
    "visualization tool. You have access to scanned file metadata, web page "
    "structure, and can search file contents. Help the user find, understand, "
    "and correlate forensic artifacts. Be concise. Reference exact file paths "
    "or URLs when relevant. When you notice two files are contextually related, "
    "say so — future versions will let you create context links."
)


class OllamaChat:
    def __init__(self, model: str = "llama3.2"):
        self.model = model
        self.history: list[dict] = []
        self._available: bool | None = None

    async def check_available(self) -> bool:
        try:
            import ollama
            ollama.list()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def build_context(self, message: str, graph) -> str:
        parts = []

        stats = graph.get_stats()
        if stats["total_nodes"] > 0:
            parts.append(f"Scanned: {graph.root_path}")
            parts.append(f"Nodes: {stats['total_nodes']}, Links: {stats['total_links']}")
            if stats.get("kinds"):
                parts.append("Types: " + ", ".join(f"{k}: {v}" for k, v in stats["kinds"].items()))

        is_web = graph.root_path and graph.root_path.startswith(("http://", "https://"))

        if is_web and graph.web_content:
            parts.append(f"\n--- Web page content ({graph.root_path}) ---")
            parts.append(graph.web_content[:4000])

            web_nodes = [n for n in graph.nodes.values() if n.kind.startswith("web_")]
            if web_nodes:
                scripts = [n for n in web_nodes if n.kind == "web_script"]
                third_party = [n for n in web_nodes if n.info.get("third_party")]
                forms = [n for n in web_nodes if n.kind == "web_form"]
                links = [n for n in web_nodes if n.kind == "web_link"]

                parts.append(f"\nPage structure:")
                parts.append(f"  Scripts: {len(scripts)} ({len([s for s in scripts if s.info.get('third_party')])} third-party)")
                parts.append(f"  Forms: {len(forms)}")
                parts.append(f"  Links: {len(links)} ({len([l for l in links if l.info.get('external')])} external)")
                parts.append(f"  Third-party resources: {len(third_party)}")

                page = next((n for n in web_nodes if n.kind == "web_page"), None)
                if page:
                    for k in ("server", "x_powered_by", "content_security_policy",
                              "strict_transport_security", "x_frame_options", "set_cookie"):
                        v = page.info.get(k)
                        if v:
                            parts.append(f"  {k}: {v}")

                if third_party:
                    domains = set(n.info.get("domain", "") for n in third_party if n.info.get("domain"))
                    parts.append(f"  Third-party domains: {', '.join(sorted(domains))}")

                # security findings
                findings = [n for n in web_nodes if n.kind == "web_finding"]
                cookies = [n for n in web_nodes if n.kind == "web_cookie"]
                if findings:
                    summary = next((n for n in findings if n.info.get("category") == "summary"), None)
                    criticals = [n for n in findings if n.info.get("severity") == "critical"]
                    warnings = [n for n in findings if n.info.get("severity") == "warning"]
                    parts.append(f"\nSecurity analysis:")
                    if summary:
                        parts.append(f"  Score: {summary.info.get('score', '?')}/100")
                    parts.append(f"  Critical: {len(criticals)}, Warnings: {len(warnings)}, Total: {len(findings)}")
                    for f in criticals[:5]:
                        parts.append(f"  [CRITICAL] {f.info.get('title', f.name)}: {f.info.get('detail', '')[:100]}")
                    for f in warnings[:5]:
                        parts.append(f"  [WARNING] {f.info.get('title', f.name)}: {f.info.get('detail', '')[:100]}")
                if cookies:
                    parts.append(f"\nCookies ({len(cookies)}):")
                    for c in cookies[:10]:
                        flags = []
                        if not c.info.get("secure"): flags.append("no-Secure")
                        if not c.info.get("httponly"): flags.append("no-HttpOnly")
                        if not c.info.get("samesite"): flags.append("no-SameSite")
                        flag_str = f" [{', '.join(flags)}]" if flags else " [OK]"
                        parts.append(f"  {c.name}{flag_str}")

        if graph.favorites:
            parts.append(f"\nFavorited nodes ({len(graph.favorites)}):")
            for nid in list(graph.favorites)[:15]:
                node = graph.nodes.get(nid)
                if node:
                    tags = list(graph.tags.get(nid, []))
                    tag_str = f" [{', '.join(tags)}]" if tags else ""
                    parts.append(f"  * {node.name} — {node.path}{tag_str}")

        tagged_count = sum(1 for t in graph.tags.values() if t)
        if tagged_count:
            all_tags = set()
            for t in graph.tags.values():
                all_tags.update(t)
            parts.append(f"\nTags in use: {', '.join(sorted(all_tags))}")

        context_links = [l for l in graph.links if l["type"] == "context"]
        if context_links:
            parts.append(f"\nContext links ({len(context_links)}):")
            for cl in context_links[:10]:
                src = graph.nodes.get(cl["source"])
                tgt = graph.nodes.get(cl["target"])
                if src and tgt:
                    parts.append(f"  {src.name} <-> {tgt.name}: {cl['label']}")

        results = graph.search(message)
        if results:
            parts.append(f"\nMatching nodes ({len(results)}):")
            for r in results[:20]:
                parts.append(f"  {r['path']} [{r['kind']}]")

        if not is_web:
            content_hits = self._grep(message, graph.root_path)
            if content_hits:
                parts.append(f"\nFiles containing '{message}':")
                for path in content_hits[:10]:
                    parts.append(f"  {path}")
                    snippet = self._read(path, 512)
                    if snippet:
                        parts.append(f"    > {snippet[:200]}")

        return "\n".join(parts) if parts else "No scan data available."

    def _grep(self, query: str, root_path: str | None) -> list[str]:
        if not root_path or not Path(root_path).is_dir():
            return []
        try:
            result = subprocess.run(
                ["grep", "-rl", "--include=*", "-m", "5", query, root_path],
                capture_output=True, text=True, timeout=10,
            )
            return [l for l in result.stdout.strip().split("\n") if l][:10]
        except Exception:
            return []

    def _read(self, path: str, max_bytes: int = 4096) -> str | None:
        try:
            p = Path(path)
            if not p.is_file() or p.stat().st_size > 1_000_000:
                return None
            return p.read_text(errors="ignore")[:max_bytes]
        except Exception:
            return None

    async def stream_response(self, message: str, graph):
        import ollama

        context = self.build_context(message, graph)
        self.history.append({"role": "user", "content": message})

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context},
            *self.history[-10:],
        ]

        try:
            stream = ollama.chat(model=self.model, messages=messages, stream=True)
            full = ""
            for chunk in stream:
                token = chunk["message"]["content"]
                full += token
                yield token
            self.history.append({"role": "assistant", "content": full})
        except Exception as e:
            log.error(f"Ollama: {e}")
            yield f"Error: {e}"

    def clear_history(self):
        self.history.clear()
