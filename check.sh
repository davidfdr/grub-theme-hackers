#!/usr/bin/env bash
# Validate this repository before installing the theme or committing a change.
#
#   ./check.sh            full check: tools, syntax, committed dist/ integrity,
#                         fresh build of every resolution, installer dry-run
#   ./check.sh --quick    skip the fresh build (validates the committed dist/ only)
#   ./check.sh --update   rebuild dist/ and previews/ in place first (contributors)
#
# Exit code 0 = everything passed. No root needed; nothing on the system is changed.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
QUICK=0; UPDATE=0
for a in "$@"; do
  case "$a" in
    --quick) QUICK=1 ;;
    --update) UPDATE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

PASS=0; FAIL=0; WARN=0
ok()   { PASS=$((PASS + 1)); printf '  \033[1;32mok\033[0m    %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf '  \033[1;31mFAIL\033[0m  %s\n' "$*"; }
warn() { WARN=$((WARN + 1)); printf '  \033[1;33mwarn\033[0m  %s\n' "$*"; }
section() { printf '\n\033[1m%s\033[0m\n' "$*"; }

REQUIRED_FILES=(theme.txt background.png menu.pf2 small.pf2
  select_c.png select_n.png select_s.png select_e.png select_w.png select_ne.png select_nw.png select_se.png select_sw.png
  icons/ubuntu.png icons/gnu-linux.png icons/windows.png icons/memtest.png icons/os.png)

png_size() {  # prints "WxH" of a PNG from its IHDR chunk
  od -An -tu4 --endian=big -j16 -N8 "$1" 2>/dev/null | awk '{print $1"x"$2}'
}

validate_theme_dir() {  # validate_theme_dir DIR  (DIR basename must be WxH)
  local d="$1" res; res="$(basename "$d")"; local problems=0
  [[ "$res" =~ ^[0-9]+x[0-9]+$ ]] || { fail "$d: directory name is not WIDTHxHEIGHT"; return; }
  for f in "${REQUIRED_FILES[@]}"; do
    [ -s "$d/$f" ] || { fail "$res: missing or empty $f"; problems=1; }
  done
  [ "$problems" = 1 ] && return
  head -c 4 "$d/background.png" | grep -q PNG || { fail "$res: background.png is not a PNG"; problems=1; }
  local got; got="$(png_size "$d/background.png")"
  [ "$got" = "$res" ] || { fail "$res: background.png is ${got:-unknown}, expected $res"; problems=1; }
  # every font named in theme.txt must exist inside a .pf2 of that directory
  local fontname
  while IFS= read -r fontname; do
    LC_ALL=C grep -aq -- "$fontname" "$d"/*.pf2 || { fail "$res: theme.txt names font \"$fontname\" but no .pf2 provides it"; problems=1; }
  done < <(grep -oE '(item_)?font = "[^"]+"|terminal-font: "[^"]+"' "$d/theme.txt" | sed -E 's/.*"([^"]+)"/\1/' | sort -u)
  # files referenced by theme.txt
  local img; img="$(grep -oE 'desktop-image: "[^"]+"' "$d/theme.txt" | sed -E 's/.*"([^"]+)"/\1/')"
  [ -n "$img" ] && [ -s "$d/$img" ] || { fail "$res: desktop-image '$img' not found"; problems=1; }
  grep -q 'selected_item_pixmap_style = "select_\*.png"' "$d/theme.txt" || { fail "$res: theme.txt does not reference select_*.png"; problems=1; }
  grep -q '^+ boot_menu' "$d/theme.txt" && grep -q '^+ progress_bar' "$d/theme.txt" || { fail "$res: theme.txt lacks boot_menu or progress_bar"; problems=1; }
  [ "$problems" = 0 ] && ok "$res: $(du -sh "$d" | cut -f1), all files present, fonts and references consistent"
}

# ---------------------------------------------------------------- tools
section "Tools"
CAN_BUILD=1
if command -v python3 >/dev/null; then ok "python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"; else fail "python3 not found"; CAN_BUILD=0; fi
if python3 -c 'import PIL' 2>/dev/null; then ok "Pillow $(python3 -c 'import PIL;print(PIL.__version__)')"; else warn "Pillow not installed (python3-pil / python3-pillow); building is not possible, prebuilt dist/ still can be installed"; CAN_BUILD=0; fi
MKFONT="$(command -v grub-mkfont || command -v grub2-mkfont || true)"
if [ -n "$MKFONT" ]; then ok "$(basename "$MKFONT") found"; else warn "grub-mkfont not found (grub-common / grub2-tools / grub); building is not possible"; CAN_BUILD=0; fi
if command -v update-grub >/dev/null || command -v grub2-mkconfig >/dev/null || command -v grub-mkconfig >/dev/null; then ok "GRUB config tool present (install.sh will work here)"; else warn "no update-grub/grub2-mkconfig/grub-mkconfig; install.sh cannot run on this machine"; fi
for f in fonts/0xProto-Regular.ttf fonts/0xProto-Bold.ttf fonts/Michroma-Regular.ttf fonts/LICENSE-0xProto.txt fonts/LICENSE-Michroma-OFL.txt; do
  [ -s "$f" ] && ok "$f" || fail "missing $f"
done

# ---------------------------------------------------------------- syntax
section "Syntax"
if [ "$CAN_BUILD" = 1 ] || command -v python3 >/dev/null; then
  python3 -B -m py_compile build.py 2>/dev/null && ok "build.py compiles" || fail "build.py does not compile"
fi
for s in install.sh uninstall.sh check.sh; do bash -n "$s" && ok "$s syntax" || fail "$s has a syntax error"; done

# ---------------------------------------------------------------- optional rebuild in place
if [ "$UPDATE" = 1 ]; then
  section "Rebuilding dist/ and previews/ in place"
  if [ "$CAN_BUILD" = 1 ]; then
    python3 -B build.py --all --preview >/dev/null && ok "python3 build.py --all --preview" || fail "build.py --all --preview failed"
  else
    fail "--update requested but build tools are missing"
  fi
fi

# ---------------------------------------------------------------- committed assets
section "Committed assets (dist/)"
if [ -d dist ] && [ -n "$(ls -A dist 2>/dev/null)" ]; then
  for d in dist/*/; do validate_theme_dir "${d%/}"; done
  if [ "$CAN_BUILD" = 1 ]; then
    for r in $(python3 -B -c 'import build; print(" ".join(build.COMMON_RESOLUTIONS))' 2>/dev/null); do
      [ -d "dist/$r" ] || fail "dist/ lacks $r although build.py lists it in COMMON_RESOLUTIONS"
    done
  fi
  for p in dist/*/; do r="$(basename "$p")"; [ -s "previews/preview-$r.png" ] || warn "previews/preview-$r.png missing (run: ./check.sh --update)"; done
else
  fail "dist/ is empty; run: python3 build.py --all --preview"
fi

# ---------------------------------------------------------------- fresh build
if [ "$QUICK" = 0 ] && [ "$CAN_BUILD" = 1 ]; then
  section "Fresh build of every resolution (temporary directory)"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  if python3 -B build.py --all --out "$TMP" >/dev/null 2>"$TMP/err.log"; then
    ok "build.py --all succeeded"
    for d in "$TMP"/*/; do validate_theme_dir "${d%/}"; done
    for d in "$TMP"/*/; do r="$(basename "$d")"; [ -d "dist/$r" ] || warn "fresh build produced $r which is not in dist/ (commit it with --update)"; done
  else
    fail "build.py --all failed: $(tail -n 3 "$TMP/err.log" | tr '\n' ' ')"
  fi
elif [ "$QUICK" = 1 ]; then
  section "Fresh build skipped (--quick)"
fi

# ---------------------------------------------------------------- installer
section "Installer dry-run (changes nothing)"
if ./install.sh --dry-run --res 1920x1080 --timeout 5 >/dev/null 2>&1; then ok "install.sh --dry-run --res 1920x1080"; else fail "install.sh --dry-run --res 1920x1080 exited non-zero"; fi
if out="$(./install.sh --dry-run 2>&1)"; then
  det="$(printf '%s\n' "$out" | grep -oE '(detected screen resolution:?|using) [0-9]+x[0-9]+' | head -n1)"
  ok "install.sh --dry-run (${det:-resolution detection ran})"
else
  fail "install.sh --dry-run (auto-detect) exited non-zero"
fi
./uninstall.sh --help >/dev/null 2>&1 && ok "uninstall.sh --help" || fail "uninstall.sh --help failed"

# ---------------------------------------------------------------- summary
printf '\n\033[1mSummary:\033[0m %d passed, %d warnings, %d failed\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "Fix the failures above before installing or committing."; exit 1
fi
echo "All good. Install with: sudo ./install.sh [--timeout N] [--hide-memtest]"
