# AGENTS.md — working on grub-theme-hackers

This file is for AI coding agents and for humans who want the short version.
Read it before changing anything.

## What this project is

A GRUB 2 graphical theme in the spirit of the 1995 film *Hackers*: black
screen, neon green perspective grid, scanlines, a wireframe alien head, a
motto, a translucent menu panel with a glowing selection box, and the three
famous handles rendered in a wide Eurostile-style face with horizontal glitch
cuts. Everything is **generated** by `build.py` with Pillow; nothing is drawn
by hand. The same design is produced for any resolution because every
position is a fraction of the screen and every size is scaled by screen height
(`s = height / 1600`, the design reference was 2560x1600).

## Repository map

| Path | Purpose |
|---|---|
| `build.py` | The generator. One `ThemeBuilder` per resolution; layers are small methods (`grid`, `hex_rain`, `alien`, `motto`, `panel`, `handles`, `footer`, `scanlines`), plus `selection_pixmaps`, `icons`, `pf2_fonts`, `theme_txt`, `preview`. |
| `install.sh` | Root installer. Detects GRUB flavour (update-grub / grub2-mkconfig / grub-mkconfig), detects the panel resolution from `/sys/class/drm`, picks `dist/<WxH>` or builds it, copies to `<grub dir>/themes/hackers`, edits `/etc/default/grub` (backup first, every managed line tagged), regenerates grub.cfg. `--dry-run` prints the plan and changes nothing. |
| `uninstall.sh` | Removes the theme dir and the tagged lines (or restores the newest backup with `--restore-backup`), regenerates grub.cfg. |
| `fonts/` | Vendored fonts: 0xProto Regular/Bold and Michroma, both SIL OFL 1.1, with their license files. Do not add fonts without a redistributable license file next to them. |
| `dist/<WxH>/` | Prebuilt theme for each common resolution: `theme.txt`, `background.png`, `select_*.png` (9-slice), `icons/*.png`, `menu.pf2`, `small.pf2`. Generated; never hand-edit. |
| `previews/` | 1280px-wide simulated renders used by the README. Generated with `--preview`. |
| `check.sh` | The validation gate (no hosted CI). Checks tools, syntax, every `dist/<WxH>` (required files, PNG size equals the directory name, font names in `theme.txt` exist in the `.pf2` files), rebuilds all resolutions in a temp dir, dry-runs the installer. `--quick` skips the rebuild, `--update` regenerates `dist/` and `previews/` in place first. Users run it before installing; contributors before committing. |

## Commands

```bash
# build one resolution (writes dist/1920x1080/)
python3 build.py --res 1920x1080

# rebuild everything that is committed (dist/ and previews/)
python3 build.py --all --preview

# try the installer without touching the system
./install.sh --dry-run --res 1920x1080 --timeout 5

# install for real (needs root), uninstall
sudo ./install.sh --timeout 5 --hide-memtest
sudo ./uninstall.sh

# THE gate: run before installing and before every commit
./check.sh            # validate as a user would (tools, syntax, dist/, fresh build, dry-run)
./check.sh --update   # contributors: regenerate dist/ + previews/ in place, then validate
```

Dependencies: `python3-pil` (Pillow) and `grub-mkfont` (package `grub-common`
on Debian/Ubuntu, `grub2-tools` on Fedora, `grub` on Arch).

## Rules

1. **Change the design in `build.py`, then regenerate `dist/` and `previews/`
   for all resolutions** (`--all --preview`) and commit them together. A PR
   that edits one but not the other is wrong.
2. Keep layout in fractions of W/H and sizes through `self.px()`. Never
   hard-code pixel values that would only be right at one resolution.
3. Text is configurable via CLI flags (`--motto`, `--handle`, `--quote`,
   `--help-text`, `--countdown`). Defaults are the shipped design; do not
   change defaults without updating README.md.
4. No trademarked logos. The alien head is an original wireframe drawing; keep
   it that way. Film quotes and handles are short references used as fan
   tribute.
5. `install.sh` must stay safe: back up `/etc/default/grub`, tag every line it
   writes with `# managed by grub-theme-hackers`, never remove unrelated
   settings, and keep `--dry-run` accurate. `check.sh` dry-runs it on every
   run; keep that passing.
6. Never run `install.sh` for real from `check.sh`, automation or a container;
   GRUB is host state. There is deliberately no hosted CI (GitHub Actions is
   disabled on the repository); `check.sh` replaces it.
7. `theme.txt` is written by `theme_txt()` in `build.py`; edit the template
   there, not the generated files.
8. Fonts: PF2 files come from `grub-mkfont` at build time with the name
   `"Hackers Menu Regular <px>"` / `"Hackers Small Regular <px>"`. The names in
   `theme.txt` must match exactly, including the pixel size.

## GRUB facts that bite

- Ubuntu's `30_os-prober` forces `timeout_style=menu` when another OS is found
  and raises `GRUB_TIMEOUT=0` to 10 s. A 0 timeout therefore does not mean
  "no menu" on dual-boot machines.
- `GRUB_TIMEOUT_STYLE=hidden` hides the menu, and with it the theme; the
  installer sets `menu`.
- `GRUB_TERMINAL=console` disables gfxterm and the theme; the installer
  comments it out with a note.
- `GRUB_GFXMODE` should be the panel's native mode with `auto` as fallback.
  If the firmware does not support the mode, GRUB falls back and
  `desktop-image-scale-method: stretch` keeps the background full-screen.
- Supported image formats are PNG, JPEG and TGA. Keep `background.png` as
  8-bit RGB PNG.

## Adding a resolution

Add it to `COMMON_RESOLUTIONS` in `build.py`, run `./check.sh --update`, add a
row to the README table, commit `dist/<WxH>/` and `previews/preview-<WxH>.png`.

## PR checklist

- [ ] `./check.sh --update` passes with 0 failures (it compiles, builds all
      resolutions, validates `dist/`, dry-runs the installer)
- [ ] regenerated `dist/` and `previews/` are committed with the code change
- [ ] README table and flags documentation match the code
- [ ] commit is GPG-signed
