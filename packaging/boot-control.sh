#!/bin/sh
set -eu
umask 077
base=/home/root/remarkable-infinite-horizontal
name=remarkable-infinite-horizontal.service
source="$base/remarkable-infinite-horizontal.service"
target="/etc/systemd/system/$name"
link="/etc/systemd/system/multi-user.target.wants/$name"
action="${1:?Expected enable or disable}"
case "$action" in enable|disable) ;; *) exit 2 ;; esac
[ "$(uname -m)" = aarch64 ]
grep -qx 'IMG_VERSION="3.28.0.172"' /etc/os-release
grep -qx 'VERSION_ID=5.8.203' /etc/os-release
[ -f "$base/.managed" ]
[ -f "$base/state/backup-complete" ]
if [ -e "$target" ] || [ -L "$target" ]; then
    [ ! -L "$target" ] && cmp -s "$target" "$source" || {
        printf '%s\n' 'Refusing to overwrite an unrecognized boot service.' >&2
        exit 1
    }
fi
if [ -e "$link" ] || [ -L "$link" ]; then
    [ "$(readlink "$link")" = "../$name" ] || [ "$(readlink "$link")" = "$target" ] || exit 1
fi
overlay_options=$(awk '$2=="/etc" && $3=="overlay" {print $4}' /proc/mounts)
[ -n "$overlay_options" ]
case "$overlay_options" in *lowerdir=/etc,upperdir=/var/volatile/etc,workdir=/var/volatile/.etc-work*) ;; *) exit 1 ;; esac
root_options=$(awk '$2=="/" {print $4}' /proc/mounts)
case "$root_options" in ro,*) ;; *) printf '%s\n' 'Root must start read-only.' >&2; exit 1 ;; esac
overlay_removed=false

restore_mounts() {
    status="$?"
    trap - EXIT HUP INT TERM
    if [ "$overlay_removed" = true ]; then
        if ! mount -t overlay overlay -o "$overlay_options" /etc; then
            printf '%s\n' 'Failed to restore /etc overlay.' >&2
            status=1
        fi
    fi
    if ! mount -o remount,ro /; then
        printf '%s\n' 'Failed to restore read-only root.' >&2
        status=1
    fi
    exit "$status"
}
trap restore_mounts EXIT
trap 'exit 1' HUP INT TERM
mount -o remount,rw /
umount -R /etc
overlay_removed=true
mkdir -p /etc/systemd/system/multi-user.target.wants
if [ "$action" = enable ]; then
    cp "$source" "$target.partial"
    chmod 0644 "$target.partial"
    mv "$target.partial" "$target"
    if [ ! -L "$link" ]; then
        ln -s "../$name" "$link"
    fi
else
    if [ -L "$link" ]; then rm "$link"; fi
    if [ -f "$target" ]; then rm "$target"; fi
fi
systemctl daemon-reload
if [ "$action" = enable ]; then
    systemctl is-enabled --quiet "$name"
fi
printf 'Automatic activation %sd. Mount state will be restored before exit.\n' "$action"
