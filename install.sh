#!/usr/bin/env bash
# Install the "Hackers" GRUB theme.
#   sudo ./install.sh [--res WxH] [--timeout N] [--hide-memtest] [--theme-dir DIR] [--dry-run]
# Works on Debian/Ubuntu (update-grub), Fedora/RHEL (grub2-mkconfig) and Arch (grub-mkconfig).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RES=""; TIMEOUT=""; HIDE_MEMTEST=0; THEME_DIR=""; DRY=0
TAG="# managed by grub-theme-hackers"

usage() { sed -n '2,5p' "$0"; exit "${1:-0}"; }
log() { printf '\033[1;32m[hackers]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hackers]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[hackers]\033[0m %s\n' "$*" >&2; exit 1; }
run() { if [ "$DRY" = 1 ]; then echo "  (dry-run) $*"; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --res) RES="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --hide-memtest) HIDE_MEMTEST=1; shift ;;
    --theme-dir) THEME_DIR="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

[ "$(id -u)" = 0 ] || [ "$DRY" = 1 ] || die "run as root: sudo $0 $*"

# --- which GRUB flavour? ---
if command -v update-grub >/dev/null 2>&1; then
  MKCONFIG=(update-grub); GRUB_DIR=/boot/grub
elif command -v grub2-mkconfig >/dev/null 2>&1; then
  GRUB_DIR=/boot/grub2; CFG=/boot/grub2/grub.cfg
  [ -f /boot/efi/EFI/fedora/grub.cfg ] && ! grep -q 'configfile' /boot/efi/EFI/fedora/grub.cfg 2>/dev/null && CFG=/boot/efi/EFI/fedora/grub.cfg
  MKCONFIG=(grub2-mkconfig -o "$CFG")
elif command -v grub-mkconfig >/dev/null 2>&1; then
  MKCONFIG=(grub-mkconfig -o /boot/grub/grub.cfg); GRUB_DIR=/boot/grub
else
  die "no update-grub / grub2-mkconfig / grub-mkconfig found; is this a GRUB system?"
fi
THEME_DIR="${THEME_DIR:-$GRUB_DIR/themes/hackers}"
DEFAULT_GRUB=/etc/default/grub
[ -f "$DEFAULT_GRUB" ] || die "$DEFAULT_GRUB not found"

# --- resolution ---
detect_res() {
  local m
  for c in /sys/class/drm/card*-eDP-* /sys/class/drm/card*-*; do
    [ -e "$c/status" ] || continue
    [ "$(cat "$c/status")" = connected ] || continue
    m="$(head -n1 "$c/modes" 2>/dev/null || true)"
    [ -n "$m" ] && { echo "$m"; return 0; }
  done
  return 1
}
if [ -z "$RES" ]; then
  if RES="$(detect_res)"; then log "detected screen resolution: $RES"; else RES=1920x1080; warn "could not detect the screen; using $RES (override with --res WxH)"; fi
fi
[[ "$RES" =~ ^[0-9]+x[0-9]+$ ]] || die "bad --res '$RES', expected WIDTHxHEIGHT"

# --- pick or build the assets ---
SRC="$HERE/dist/$RES"
if [ ! -f "$SRC/theme.txt" ]; then
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import PIL' 2>/dev/null && (command -v grub-mkfont || command -v grub2-mkfont) >/dev/null 2>&1; then
    log "no prebuilt assets for $RES; building them now"
    run python3 "$HERE/build.py" --res "$RES" --out "$HERE/dist"
  else
    # fall back to the closest prebuilt resolution with the same aspect ratio
    want_w=${RES%x*}; want_h=${RES#*x}; best=""; best_d=999999
    for d in "$HERE"/dist/*/; do
      r=$(basename "$d"); w=${r%x*}; h=${r#*x}
      if [ $((w * want_h)) -eq $((h * want_w)) ]; then
        dd=$(( h > want_h ? h - want_h : want_h - h ))
        [ "$dd" -lt "$best_d" ] && { best_d=$dd; best=$r; }
      fi
    done
    [ -n "$best" ] || best=1920x1080
    warn "no assets for $RES and cannot build (need python3-pil + grub-mkfont); using $best, GRUB will stretch it"
    SRC="$HERE/dist/$best"
  fi
fi
[ -f "$SRC/theme.txt" ] || [ "$DRY" = 1 ] || die "theme assets not found at $SRC"

# --- copy theme ---
log "installing theme files to $THEME_DIR"
run mkdir -p "$(dirname "$THEME_DIR")"
if [ "$DRY" = 0 ]; then
  rm -rf "$THEME_DIR.new"; cp -r "$SRC" "$THEME_DIR.new"
  [ -d "$THEME_DIR" ] && rm -rf "$THEME_DIR.old" && mv "$THEME_DIR" "$THEME_DIR.old"
  mv "$THEME_DIR.new" "$THEME_DIR"; rm -rf "$THEME_DIR.old"
  chmod -R u=rwX,go=rX "$THEME_DIR"
else
  echo "  (dry-run) copy $SRC -> $THEME_DIR"
fi

# --- /etc/default/grub ---
set_kv() {  # set_kv KEY VALUE   (replaces the active line or appends a tagged one)
  local key="$1" val="$2"
  if [ "$DRY" = 1 ]; then echo "  (dry-run) $key=$val"; return; fi
  if grep -qE "^${key}=" "$DEFAULT_GRUB"; then
    sed -i -E "s|^${key}=.*|${key}=${val}   ${TAG}|" "$DEFAULT_GRUB"
  else
    printf '%s=%s   %s\n' "$key" "$val" "$TAG" >> "$DEFAULT_GRUB"
  fi
}
BACKUP="$DEFAULT_GRUB.bak-hackers-$(date +%Y%m%d-%H%M%S)"
log "backing up $DEFAULT_GRUB to $BACKUP"
run cp -a "$DEFAULT_GRUB" "$BACKUP"
set_kv GRUB_THEME "\"$THEME_DIR/theme.txt\""
set_kv GRUB_GFXMODE "${RES},auto"
set_kv GRUB_TIMEOUT_STYLE menu
[ -n "$TIMEOUT" ] && set_kv GRUB_TIMEOUT "$TIMEOUT"
[ "$HIDE_MEMTEST" = 1 ] && set_kv GRUB_DISABLE_MEMTEST true
if grep -qE '^GRUB_TERMINAL(_OUTPUT)?=.*console' "$DEFAULT_GRUB"; then
  warn "GRUB_TERMINAL is set to console; a graphical theme needs gfxterm. Commenting that line out."
  run sed -i -E "s|^(GRUB_TERMINAL(_OUTPUT)?=.*console.*)|# \1   (disabled by grub-theme-hackers)|" "$DEFAULT_GRUB"
fi
if grep -qE '^GRUB_TIMEOUT=0\b' "$DEFAULT_GRUB"; then
  warn "GRUB_TIMEOUT=0: the menu (and the theme) will not be shown unless you hold Shift/Esc. Use --timeout N to change it."
fi

# --- regenerate grub.cfg ---
log "regenerating GRUB configuration: ${MKCONFIG[*]}"
run "${MKCONFIG[@]}"
if [ "$DRY" = 0 ]; then
  cfg="${CFG:-$GRUB_DIR/grub.cfg}"
  grep -q "themes/hackers/theme.txt" "$cfg" 2>/dev/null && log "done. Theme active in $cfg; reboot to see it." || warn "grub.cfg does not reference the theme; check $DEFAULT_GRUB"
else
  log "dry-run complete; nothing was changed."
fi
