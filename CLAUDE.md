# CLAUDE.md

@AGENTS.md

Notes for Claude Code specifically:

- Start with `AGENTS.md` above; it is the source of truth for structure, commands and rules.
- Before committing a design change, run `python3 build.py --all --preview` and look at
  `previews/preview-2560x1600.png` and `previews/preview-1920x1080.png` (use the Read tool on
  the PNG) to check the layout visually. The preview is a simulation of GRUB's rendering;
  spacing in real GRUB can differ slightly, which is fine.
- Never run `sudo ./install.sh` on the developer's machine unless they ask; use `--dry-run`.
- When touching `install.sh`, keep it POSIX-friendly bash (`set -euo pipefail`, no GNU-only
  flags beyond `sed -i -E` and `date +%Y%m%d-%H%M%S`), because it runs on Debian, Fedora and Arch.
- Commit generated assets (`dist/`, `previews/`) in the same commit as the code change that
  produced them.
