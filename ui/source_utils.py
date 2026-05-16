EXCERPT_LIMIT = 8000  # chars per source when no summary exists


def build_sources_prompt(sources):
    """Return a prompt string for the given source rows, using summaries where available."""
    if not sources:
        return ''
    parts = []
    for r in sources:
        filename = r['filename']
        summary = r['summary'] if r['summary'] else ''
        if summary:
            parts.append(f"SOURCE: {filename}\n\n{summary}")
        else:
            excerpt = r['content'][:EXCERPT_LIMIT]
            truncated = len(r['content']) > EXCERPT_LIMIT
            note = f"\n\n[Truncated — only first {EXCERPT_LIMIT} chars shown. Use 'Summarise for AI' in Sources tab for full coverage.]" if truncated else ''
            parts.append(f"SOURCE: {filename}\n\n{excerpt}{note}")
    return '\n\n---\n\n'.join(parts)
