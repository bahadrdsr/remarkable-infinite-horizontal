#!/bin/sh
set -eu
umask 077

base=/home/root/remarkable-infinite-horizontal
state="$base/state"
runtime=/run/systemd/system
unit_source=/usr/lib/systemd/system/xochitl.service
dropin_source=/usr/lib/systemd/system/xochitl.service.d/xochitl-service-override.conf
unit="$runtime/xochitl.service"
dropin="$runtime/xochitl.service.d/xochitl-service-override.conf"
recovery="$runtime/infinite-horizontal-recovery.service"
lock=/run/infinite-horizontal-transition
marker='# remarkable-infinite-horizontal managed runtime'
action="${1:-status}"

log() { printf '[infinite-horizontal] %s\n' "$*"; }
die() { log "$*" >&2; exit 1; }

compatible() {
    [ "$(uname -m)" = aarch64 ] &&
    [ "$(tr '\000' '\n' < /sys/firmware/devicetree/base/model)" = 'reMarkable Tatsu' ] &&
    grep -qx 'IMG_VERSION="3.28.0.172"' /etc/os-release &&
    grep -qx 'VERSION_ID=5.8.203' /etc/os-release
}

load_release() {
    release=$(cat "$base/selected-release")
    case "$release" in *[!0-9a-f]*|'') die 'Invalid selected release.' ;; esac
    [ "${#release}" = 16 ] || die 'Invalid selected release length.'
    path="$base/releases/$release"
    (cd "$path" && sha256sum -c SHA256SUMS) >/dev/null
    (cd / && sha256sum -c "$path/vendor.sha256") >/dev/null
}

owned() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(head -n 1 "$1")" = "$marker" ]
}

check_overrides() {
    for file in "$unit" "$dropin" "$recovery"; do
        if [ -e "$file" ] || [ -L "$file" ]; then
            owned "$file" || die "Refusing to replace unowned runtime configuration: $file"
        fi
    done
    fragment=$(systemctl show xochitl.service -p FragmentPath --value)
    [ "$fragment" = "$unit_source" ] || [ "$fragment" = "$unit" ] || die 'Unknown stock unit.'
    drops=$(systemctl show xochitl.service -p DropInPaths --value)
    [ "$drops" = "$dropin_source" ] || [ "$drops" = "$dropin" ] || die 'Unreviewed stock drop-ins are present.'
}

take_lock() {
    if ! mkdir "$lock" 2>/dev/null; then
        if [ -f "$lock/pid" ]; then
            previous=$(cat "$lock/pid")
            case "$previous" in *[!0-9]*|'') die 'Invalid transition lock.' ;; esac
            if kill -0 "$previous" 2>/dev/null; then
                die 'Another UI transition is still running.'
            fi
            rm "$lock/pid"
            rmdir "$lock"
            mkdir "$lock"
        else
            die 'Unowned UI transition lock.'
        fi
    fi
    printf '%s\n' "$$" > "$lock/pid"
}

unlock() {
    if [ -f "$lock/pid" ] && [ "$(cat "$lock/pid")" = "$$" ]; then
        rm "$lock/pid"
        rmdir "$lock"
    fi
}

write_shadow() {
    mode="$1"
    mkdir -p "$runtime/xochitl.service.d"
    {
        printf '%s\n' "$marker"
        sed '/^[[:space:]]*OnFailure[[:space:]]*=/d' "$unit_source"
        printf '\n[Service]\nRestart=no\n'
        if [ "$mode" = patched ]; then
            printf 'Environment="XOVI_ROOT=%s/runtime"\n' "$path"
            printf 'Environment="LD_PRELOAD=%s/runtime/xovi.so:%s/bin/libinfinite-settings.so:%s/bin/libnative-inspector.so"\n' "$path" "$path" "$path"
            printf 'Environment="QML_DISABLE_DISK_CACHE=1"\n'
            printf 'Environment="INFINITE_HORIZONTAL_INSPECTION=%s"\n' "$inspection"
            if [ "$kind" = capture ]; then
                printf 'Environment="INFINITE_HORIZONTAL_CAPTURE=1"\n'
            fi
            printf '\n[Unit]\nOnFailure=infinite-horizontal-recovery.service\n'
        fi
    } > "$unit.partial"
    {
        printf '%s\n' "$marker"
        sed '/^[[:space:]]*OnFailure[[:space:]]*=/d' "$dropin_source"
    } > "$dropin.partial"
    chmod 0644 "$unit.partial" "$dropin.partial"
    mv "$unit.partial" "$unit"
    mv "$dropin.partial" "$dropin"
    systemctl daemon-reload
}

stop_editor() {
    write_shadow guard
    [ -z "$(systemctl show xochitl.service -p OnFailure --value)" ] || die 'Shutdown guard did not take effect.'
    if ! systemctl stop xochitl.service; then
        log 'Stock stop reported failure; checking whether all processes exited.'
    fi
    [ "$(systemctl show xochitl.service -p MainPID --value)" = 0 ] || die 'Stock process is still running.'
    [ "$(systemctl show xochitl.service -p ControlPID --value)" = 0 ] || die 'Stock control process is still running.'
    result=$(systemctl show xochitl.service -p Result --value)
    if [ "$result" = core-dump ]; then
        [ "$(systemctl show xochitl.service -p ExecMainStatus --value)" = 11 ] || die 'Unexpected stock crash.'
        log 'Contained stock SIGSEGV during intentional shutdown.'
    elif [ "$result" != success ] && [ "${1:-}" = recovery ]; then
        log "Restoring stock after service result: $result"
    elif [ "$result" != success ]; then
        die "Unexpected stock stop result: $result"
    fi
    systemctl reset-failed xochitl.service
}

restore_stock() {
    check_overrides
    if owned "$unit" || owned "$dropin"; then
        stop_editor recovery
        rm "$unit" "$dropin"
        systemctl daemon-reload
    fi
    systemctl reset-failed xochitl.service
    systemctl start xochitl.service
    systemctl is-active --quiet xochitl.service
    [ "$(systemctl show xochitl.service -p FragmentPath --value)" = "$unit_source" ]
    [ "$(systemctl show xochitl.service -p DropInPaths --value)" = "$dropin_source" ]
    rm -f "$state/incomplete" "$state/active"
    printf '%s %s\n' "$(date +%s)" "$(cat /proc/sys/kernel/random/boot_id)" > "$state/last-transition"
    log 'Original stock service restored.'
}

activation_exit() {
    status="$?"
    trap - EXIT HUP INT TERM
    if [ "$status" -ne 0 ]; then
        log 'Activation failed. Disabling automatic activation and restoring stock.'
        touch "$base/disabled"
        if [ -n "${token:-}" ]; then
            systemctl stop "infinite-horizontal-deadline-$token.timer" 2>/dev/null || true
        fi
        if ! (set -eu; restore_stock); then
            log 'Immediate restoration failed. The independent recovery deadline remains armed.' >&2
        fi
    fi
    unlock
    exit "$status"
}

case "$action" in
    status)
        systemctl show xochitl.service -p ActiveState -p MainPID -p FragmentPath -p DropInPaths
        systemctl show rm-sync.service -p ActiveState
        if [ -f "$base/disabled" ]; then log 'Automatic activation disabled.'; fi
        if [ -f "$state/active" ]; then cat "$state/active"; fi
        exit 0
        ;;
    boot)
        if ! compatible; then log 'Unverified firmware; keeping stock.'; exit 0; fi
        if [ -e "$base/disabled" ]; then log 'Disabled; keeping stock.'; exit 0; fi
        if [ -e "$state/incomplete" ]; then
            touch "$base/disabled"
            log 'Previous startup did not complete; keeping stock.'
            exit 0
        fi
        [ -e "$state/backup-complete" ] || die 'No installation backup receipt.'
        ;;
    activate)
        [ "${2:-}" = guard-approved ] || die 'Explicit shutdown guard approval is required.'
        compatible || die 'Unverified hardware or software.'
        ;;
    stock|disable|recover)
        mkdir -p "$state"
        if [ "$action" != stock ]; then touch "$base/disabled"; fi
        take_lock
        trap unlock EXIT
        restore_stock
        exit 0
        ;;
    *) die 'Unknown manager action.' ;;
esac

load_release
mkdir -p "$state" "$base/inspection"
check_overrides
if owned "$unit" && [ -f "$state/active" ] && systemctl is-active --quiet xochitl.service; then
    log 'Already active.'
    exit 0
fi
systemctl is-active --quiet xochitl.service
if [ -f "$state/last-transition" ]; then
    set -- $(cat "$state/last-transition")
    previous_time="${1:-0}"
    previous_boot="${2:-legacy}"
    case "$previous_time" in *[!0-9]*|'') die 'Invalid transition timestamp.' ;; esac
    current_boot=$(cat /proc/sys/kernel/random/boot_id)
    if [ "$previous_boot" = "$current_boot" ] ||
        { [ "$previous_boot" = legacy ] && [ "$action" != boot ]; }; then
        elapsed=$(($(date +%s) - previous_time))
        [ "$elapsed" -ge 180 ] || die 'Wait three minutes between UI transitions.'
    fi
fi
take_lock
trap activation_exit EXIT
trap 'exit 1' HUP INT TERM
kind=$(cat "$path/kind")
case "$kind" in capture|patch) ;; *) die 'Invalid release kind.' ;; esac
token=$(cat /proc/sys/kernel/random/uuid | tr -d '-')
inspection="$base/inspection/$token"
printf '%s\n' "$token" > "$state/incomplete"
{
    printf '%s\n' "$marker"
    printf '[Unit]\nDescription=Restore stock after infinite canvas fails\n'
    printf '[Service]\nType=oneshot\nRestart=no\nTimeoutStartSec=120\n'
    printf 'ExecStart=/bin/sh %s/manager.sh recover\n' "$base"
} > "$recovery"
chmod 0644 "$recovery"
systemctl daemon-reload
systemd-run --quiet --unit="infinite-horizontal-deadline-$token" --on-active=180s \
    --timer-property=AccuracySec=1s /bin/sh "$base/manager.sh" recover
systemctl is-active --quiet "infinite-horizontal-deadline-$token.timer"
pid=$(systemctl show xochitl.service -p MainPID --value)
"$path/bin/infinite-idle" "$pid"
[ "$(systemctl show xochitl.service -p MainPID --value)" = "$pid" ]
stop_editor
if [ "$action" = activate ]; then
    "$path/bin/native-document-snapshot" --all "$base/backups/$token" > "$state/notebooks"
    touch "$state/backup-complete"
fi
write_shadow patched
systemctl start xochitl.service
ready=false
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if ! systemctl is-active --quiet xochitl.service; then die 'Modified stock process stopped.'; fi
    if [ -s "$inspection/index.json" ]; then
        if "$path/bin/infinite-verify" "$path/manifest.json" "$inspection/index.json"; then
            ready=true
            break
        fi
    fi
    sleep 1
done
[ "$ready" = true ] || die 'Native resources did not become ready.'
pid=$(systemctl show xochitl.service -p MainPID --value)
grep -Fq "$path/runtime/xovi.so" "/proc/$pid/maps"
grep -Fq "$path/bin/libinfinite-settings.so" "/proc/$pid/maps"
systemctl is-active --quiet rm-sync.service
printf '%s %s\n' "$release" "$token" > "$state/active"
rm "$state/incomplete"
rm -f "$base/disabled"
systemctl stop "infinite-horizontal-deadline-$token.timer"
log "Native editor active; document sync active; release=$release; inspection=$token"
