# BLOCKED: permit-map-destination (build run 2026-10-05)

## Task

1.1 Reset docs to the new destination: archive `docs/product-brief.md` and `docs/eval-questions.md`, write a new brief and README, apply the "CLAUDE.md replacement text" from design.md, and replace the `context:` block in `openspec/config.yaml`.

## What I tried

- Editing `CLAUDE.md` and `openspec/config.yaml` with the exact replacement text from design.md. The unattended runner's safety policy **denied** it as self-modification: these files are the agent's own operating instructions, and an unattended agent may not rewrite them.
- The `git mv` of `docs/product-brief.md` and `docs/eval-questions.md` to `docs/archive/` was denied the same way (CLAUDE.md tells agents to read both files, so they count as agent instructions too).
- I wrote a new brief and README, then reverted both so the change isn't left half done. Nothing from task 1.1 is committed. Tasks 2.1–7.1 are untouched, because CLAUDE.md says to stop work on a change once it is blocked.

This is not a problem with the spec. The task asks an unattended agent to rewrite its own instructions, and the runner won't allow that.

## Decision needed

Who applies the instruction-file part of task 1.1, and may the builder go on with tasks 2.1–7.1 in the meantime?

## Recommended answer

Adrien applies the agent-instruction edits himself: the CLAUDE.md text, the `config.yaml` context and the two `git mv`s. He can do it on `main` or in his next design session (about 5 minutes, all of the text is in design.md). The builder then writes the new `docs/product-brief.md` and `README.md` and checks off 1.1. Until then, the builder should be allowed to work on tasks 2.1–7.1 out of order. **Reason:** files that tell agents how to behave should change only with a human present, and tasks 2–7 don't depend on task 1.

To unblock, delete this file. If you edit `tasks.md` (for example, to split 1.1 into a PM part and a builder part, or to mark the instruction-file part done), the next run follows it.
