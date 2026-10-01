# seattle-semantic-layer

> **Results table goes here** once the benchmark has run. Nothing is published until it's real.

Does a documented semantic layer, rather than a better LLM, make natural-language questions over a warehouse return correct answers? This repo tests that on Seattle open data: 30 business questions, one model, one prompt, three levels of warehouse context.

Status: in design. See `docs/product-brief.md` and `openspec/changes/`.

## How this repo is built

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec). Design sessions use the `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) and `grill-me` from [mattpocock/skills](https://github.com/mattpocock/skills) (both MIT; licenses kept alongside each skill). Approved changes are implemented by agents and land as pull requests. See `CLAUDE.md`.
