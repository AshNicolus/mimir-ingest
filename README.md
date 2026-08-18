# mimir-ingest

Turns raw AI coding agent session logs into [Mimir](https://github.com/AshNicolus/mimir) experiences.

Claude Code, Cursor, and Codex all keep a raw history of every session, but it
sits in undocumented, per-tool formats nothing else can read. `mimir-ingest`
reads that history, splits each session into individual episodes of work,
classifies each one into a bucket (feature, fix, refactor, other), and stores
it as a Mimir experience, so `recommend()` and `recall()` can learn from work
you did in any of these tools, not just what you explicitly recorded.

## Where this sits

`mimir-ingest` is a satellite tool built on top of the
[Mimir](https://github.com/AshNicolus/mimir) framework, not a fork or
replacement of it:

```
              ┌────────────────────┐
   raw logs → │    mimir-ingest     │ → same store ← Mimir MCP server ← your agent
 (Claude Code,│  (this repo, a CLI) │   (~/.mimir/memory.db)   (recall/recommend)
  Cursor, ...)└────────────────────┘
```

- **mimir-learn** (the `mimir` package) is the core framework: `Mimir`,
  `record_conversation()`, `Experience`, `Distiller`, `Embedder`, transcript
  dedupe, provenance stamping. This repo depends on it (`mimir-learn>=0.1.5`)
  and never reimplements storage or dedupe logic itself.
- **Mimir MCP server** is how a running agent *reads* that store — via
  `recall()` / `recommend()`.
- **mimir-ingest** (this repo) only *writes* into that same store. It has no
  read-side API of its own: everything it classifies becomes an ordinary
  `Experience`, indistinguishable at query time from one recorded live
  through `record_conversation()`. Point both tools at the same `--db` /
  `MIMIR_DB_PATH` and an agent immediately gets recall over sessions it never
  explicitly logged.

## Install

```bash
pip install -e .
```

Requires `mimir-learn>=0.1.5`. Classification works with no model at all (a
deterministic heuristic bucketer), or plug in any local model pulled into
[Ollama](https://ollama.com) by name.

## Quick start

```bash
# 1. See what would be ingested, without writing anything
mimir-ingest run --dry-run

# 2. (optional) pull a small local model for better classification
ollama pull qwen2.5:1.5b

# 3. Ingest for real
mimir-ingest run --model qwen2.5:1.5b   # classify with the local model
mimir-ingest run                        # or skip Ollama entirely, heuristic-only

# 4. See what's in the store now
mimir-ingest report
```

Run `mimir-ingest run` again any time (e.g. after a fresh coding session) —
it's safe to re-run: Mimir's transcript-hash dedupe means re-ingesting a
session updates its existing experience in place rather than duplicating it.

## CLI reference

Global flag, valid before the subcommand:

| Flag | Default | Meaning |
|---|---|---|
| `--db PATH` | `~/.mimir/memory.db`, or `$MIMIR_DB_PATH` | Mimir store to read/write |

### `mimir-ingest run`

Reads raw sessions, segments them into episodes, classifies each, and stores
it as a Mimir experience.

| Flag | Default | Meaning |
|---|---|---|
| `--source {claude-code}` | `claude-code` | which reader to use |
| `--model TAG` | none | Ollama model tag (e.g. `qwen2.5:1.5b`); omit to use the heuristic bucketer only |
| `--limit N` | none | cap how many sessions are processed, for a quick trial run |
| `--dry-run` | off | print `[category] task -> action` per episode; write nothing |

Prints a one-line summary to stderr when done:
`<N> classified, <N> new, <N> skipped`.
`classified` can exceed `new` — that's expected, it means some episodes were
already in the store and just got their entry refreshed, not duplicated.

### `mimir-ingest report`

```bash
mimir-ingest report
```

Prints real aggregate counts straight from the store (no model call, no
narrative generation): per category, episode count, success/failure/partial
breakdown, the most common recorded action, and which agent it mostly came
from.

## How classification works

Each episode is classified into one of `feature`, `fix`, `refactor`, `other`
by whichever extractor is configured:

- **No `--model`**: the deterministic heuristic bucketer (`fallback.py`)
  keyword-matches the user's turns (e.g. "fix"/"bug" → `fix`,
  "add"/"implement" → `feature`) and always succeeds.
- **`--model TAG`**: `OllamaExtractor` sends the (compressed) episode to
  `http://localhost:11434` and asks for a one-word category plus a one-line
  task/action summary as JSON. On any network error, timeout, or unparseable
  reply it **abstains** (returns `None`) rather than raising — the heuristic
  bucketer then classifies that episode instead, so one bad response never
  stalls a whole run.

Outcome (`success` / `failure` / `partial`) is never asserted from the model —
it's inferred from the human's own trailing reaction in the transcript
(phrases like "works now" vs "still broken"), since that's a real signal
already present in the data rather than a guess.

## Pipeline

```
raw session -> Reader -> Segmenter -> Compressor -> Extractor -> Mimir
```

- **Reader**: one parser per source, normalizing tool-specific formats into
  plain turns. Tool payloads are previewed (first 200 chars), never captured
  in full — a Bash command's stdout or a Read's file contents would
  otherwise dominate an episode's size.
- **Segmenter**: splits a session into episodes by a 30-minute time gap,
  since one file can span several unrelated tasks.
- **Compressor**: deduplicates back-to-back repeats and, if an episode is
  still too large for the configured model's budget (2000 tokens by
  default), drops the middle, keeping the start (the original ask) and the
  end (how it landed).
- **Extractor**: the pluggable classification seam described above.
  Implement `Extractor` for any backend beyond Ollama; the heuristic
  bucketer always succeeds as the last resort.
- **Store**: `record_conversation()` on the Mimir side, reusing its
  existing dedupe-by-transcript-hash and provenance stamping.

## Sources

Only Claude Code (`~/.claude/projects/*/*.jsonl`) is implemented today. Cursor
and Codex readers are planned once their raw formats are confirmed against
real samples.

## Privacy

Only short previews of tool inputs/outputs (200 chars) ever leave the reader
stage — full file contents, command output, etc. are never stored or sent to
a model. Everything stays local: the store is a local SQLite-backed file and,
if `--model` is used, classification calls a locally-running Ollama, never a
hosted API.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT
