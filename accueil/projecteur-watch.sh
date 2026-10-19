#!/bin/sh
# Ouvre la page d'accueil dès que le projecteur s'allume (démarrage ou sortie de veille).
# Interroge l'ADB du projecteur toutes les 2 s ; plus rapide que Home Assistant
# (10 s) et que le démarrage de Termux (~55 s après le boot).
DEV=${DEV:-192.168.1.228:5555}
URL=${URL:-http://192.168.1.43:8099/}
export ADB_VENDOR_KEYS="${CREDENTIALS_DIRECTORY:-/etc/projecteur-watch}/adbkey"

# timeout : un appareil injoignable bloque sinon adb une vingtaine de secondes.
a() { timeout 4 adb -s "$DEV" "$@" 2>/dev/null; }
awake() { a shell dumpsys power | grep -q 'mWakefulness=Awake'; }
focus() { a shell dumpsys window | grep -m1 mCurrentFocus | grep -q tcl.browser; }

open_page() {
    # Le launcher repasse parfois devant juste après le boot : on insiste jusqu'à 30 s.
    i=0
    while [ $i -lt 6 ]; do
        focus && return
        a shell am start -a android.intent.action.VIEW -d "$URL" -p com.tcl.browser >/dev/null 2>&1
        sleep 5; i=$((i+1))
    done
}

was_awake=1  # au démarrage du service, ne rien ouvrir si le projecteur tourne déjà
while :; do
    if [ "$(a get-state)" != device ]; then
        # « offline » après une extinction : il faut se déconnecter pour se reconnecter.
        timeout 4 adb disconnect "$DEV" >/dev/null 2>&1
        timeout 4 adb connect "$DEV" >/dev/null 2>&1
    fi
    if awake; then
        [ "$was_awake" = 0 ] && { echo "projecteur allumé, ouverture de la page"; open_page; }
        was_awake=1
    else
        was_awake=0
    fi
    sleep 2
done
