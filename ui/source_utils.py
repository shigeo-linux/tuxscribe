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


def build_combined_sources_prompt(series_name, series_sources, project_sources):
    """Combine series-level and book-level sources into one labelled prompt block."""
    parts = []
    if series_sources:
        s = build_sources_prompt(series_sources)
        if s:
            parts.append(f"SERIES BIBLE & WORLD-BUILDING ({series_name}):\n\n{s}")
    if project_sources:
        p = build_sources_prompt(project_sources)
        if p:
            parts.append(f"BOOK RESEARCH SOURCES:\n\n{p}")
    return '\n\n---\n\n'.join(parts)
