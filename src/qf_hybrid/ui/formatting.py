"""Browser-safe rendering helpers for local report excerpts."""
import re


def safe_evidence_markdown(source: str) -> str:
    """Display local file references as text; retain external web links."""
    def replace(match):
        label, target = match.group(1), match.group(2).strip()
        return match.group(0) if target.startswith(("https://", "http://")) else f"**{label}**"
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", replace, source)
