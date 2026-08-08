# mimir-ingest

Turns raw AI coding agent session logs into [Mimir](https://github.com/AshNicolus/mimir) experiences.

Claude Code, Cursor, and Codex all keep a raw history of every session, but it
sits in undocumented, per-tool formats nothing else can read. `mimir-ingest`
reads that history, splits each session into individual episodes of work,
classifies each one into a bucket (feature, fix, refactor, other), and stores
it as a Mimir experience, so `recommend()` and `recall()` can learn from work
you did in any of these tools, not just what you explicitly recorded.

## Install

```bash
pip install -e .
```

Requires `mimir-learn>=0.1.5`. Classification works with no model at all (a
deterministic heuristic bucketer), or plug in any local model pulled into
[Ollama](https://ollama.com) by name.

## Use

```bash
mimir-ingest run --dry-run              # see what would be stored, write nothing
mimir-ingest run --model qwen2.5:1.5b   # ingest with a local model
mimir-ingest run                        # ingest with the heuristic bucketer only
mimir-ingest report                     # aggregate insights from what is stored
```

Defaults to `~/.mimir/memory.db` (override with `MIMIR_DB_PATH` or `--db`), the
same store the [Mimir MCP server](https://github.com/AshNicolus/mimir) uses, so
an agent you're already running can consult this history too.

## Sources

Only Claude Code (`~/.claude/projects/*/*.jsonl`) is implemented today. Cursor
and Codex readers are planned once their raw formats are confirmed against
real samples.

## Pipeline

```
raw session -> Reader -> Segmenter -> Compressor -> Extractor -> Mimir
```

- **Reader**: one parser per source, normalizing tool-specific formats into
  plain turns. Tool payloads are previewed, never captured in full.
- **Segmenter**: splits a session into episodes by time gap, since one file
  can span several unrelated tasks.
- **Compressor**: deduplicates and, if an episode is still too large for the
  configured model's budget, drops the middle, keeping the start and end.
- **Extractor**: the pluggable classification seam. Implement `Extractor` for
  any backend; `OllamaExtractor` ships built in, keyed by a plain model name.
  Abstains (returns `None`) on a timeout or unparseable reply, at which point
  the deterministic heuristic bucketer in `fallback.py` always succeeds.
- **Store**: `record_conversation()` on the Mimir side, reusing its existing
  dedupe-by-transcript-hash and provenance stamping.

## License

MIT
