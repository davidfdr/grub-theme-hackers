#!/usr/bin/env bash
# Remove the "Hackers" GRUB theme and the settings install.sh added.
#   sudo ./uninstall.sh [--theme-dir DIR] [--restore-backup]
set -euo pipefail
THEME_DIR=""; RESTORE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --theme-dir) THEME_DIR="$2"; shift 2 ;;
    --restore-backup) RESTORE=1; shift ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "run as root: sudo $0 $*" >&2; exit 1; }
if command -v update-grub >/dev/null 2>&1; then MKCONFIG=(update-grub); GRUB_DIR=/boot/grub
elif command -v grub2-mkconfig >/dev/null 2>&1; then GRUB_DIR=/boot/grub2; MKCONFIG=(grub2-mkconfig -o /boot/grub2/grub.cfg)
else MKCONFIG=(grub-mkconfig -o /boot/grub/grub.cfg); GRUB_DIR=/boot/grub; fi
THEME_DIR="${THEME_DIR:-$GRUB_DIR/themes/hackers}"
DEFAULT_GRUB=/etc/default/grub
if [ "$RESTORE" = 1 ]; then
  latest="$(ls -1t "$DEFAULT_GRUB".bak-hackers-* 2>/dev/null | head -n1 || true)"
  [ -n "$latest" ] || { echo "no backup found ($DEFAULT_GRUB.bak-hackers-*)" >&2; exit 1; }
  cp -a "$latest" "$DEFAULT_GRUB"; echo "restored $DEFAULT_GRUB from $latest"
else
  # drop only the lines we manage; leave everything else untouched
  sed -i -E '/# managed by grub-theme-hackers$/d; s|^# (GRUB_TERMINAL(_OUTPUT)?=.*)   \(disabled by grub-theme-hackers\)$|\1|' "$DEFAULT_GRUB"
  echo "removed managed settings from $DEFAULT_GRUB"
fi
[ -d "$THEME_DIR" ] && rm -rf "$THEME_DIR" && echo "removed $THEME_DIR"
"${MKCONFIG[@]}"
echo "done. GRUB is back to its default look."
