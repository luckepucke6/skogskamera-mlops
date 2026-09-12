#!/usr/bin/env bash
# infra/k3s/setup-pi4.sh — gör Pi 4 redo att köra k3s.
#
# Körs PÅ Pi 4 med sudo:
#   scp infra/k3s/setup-pi4.sh skog@skog-pi4.local:~/
#   ssh skog@skog-pi4.local sudo bash setup-pi4.sh
#
# Idempotent — går att köra flera gånger. Behövs eftersom steg 1 kräver omstart, och steg 2
# körs klart vid nästa körning.

set -euo pipefail

CMDLINE_FILE="/boot/firmware/cmdline.txt"
CGROUP_FLAGS="cgroup_memory=1 cgroup_enable=memory"
K3S_VERSION="v1.36.4+k3s1"

if [ "$(id -u)" -ne 0 ]; then
    echo "Måste köras med sudo (behöver skriva till $CMDLINE_FILE och installera k3s)." >&2
    exit 1
fi

# --- Steg 1: aktivera memory-cgroup -----------------------------------------------------
# k3s sätter minnesgränser (resources.limits.memory) på containrar via cgroups. Raspberry Pi
# OS har memory-cgroup avstängt som standard — utan den startar k3s ändå, men minnesgränser
# blir overksamma och en pod kan äta allt RAM. Flaggan sätts i cmdline.txt (boot-parametrar).
if ! grep -q "cgroup_enable=memory" "$CMDLINE_FILE"; then
    echo "Memory-cgroup är avstängd — patchar $CMDLINE_FILE och startar om."
    cp "$CMDLINE_FILE" "$CMDLINE_FILE.bak"
    # cmdline.txt är EN rad — vi lägger till flaggorna sist på den raden, inte en ny rad.
    sed -i "s/\$/ ${CGROUP_FLAGS}/" "$CMDLINE_FILE"
    echo "Klart. Kör 'sudo reboot' och kör sedan det här scriptet EN GÅNG TILL efter omstart."
    exit 0
fi

# Kollar /sys/fs/cgroup/cgroup.controllers (cgroup v2 — det här systemet kör bara v2), INTE
# gamla /proc/cgroups. /proc/cgroups kan visa "memory" som avstängd på ett v2-system trots
# att den riktiga listan redan har memory — cgroup.controllers är filen kubelet läser.
if ! grep -qw memory /sys/fs/cgroup/cgroup.controllers; then
    echo "cmdline.txt är patchad men kärnan har inte startat om med ändringen än." >&2
    echo "Kör 'sudo reboot' och försök igen." >&2
    exit 1
fi
echo "Memory-cgroup är aktiverad (cgroup.controllers: $(cat /sys/fs/cgroup/cgroup.controllers)). Fortsätter."

# --- Steg 2: installera k3s --------------------------------------------------------------
# --disable traefik: slipper Ingress-controllern k3s annars installerar — vi exponerar via
# LoadBalancer (ServiceLB) istället, sparar ~100 MB RAM.
# --tls-san: certifikatet måste innehålla mDNS-namnet skog-pi4.local, annars litar inte
# kubectl på det när vi pratar med noden från Macen.
# K3S_KUBECONFIG_MODE=644: gör k3s.yaml läsbar för `skog`, inte bara root, så vi slipper
# sudo för att kopiera filen till Macen.
if command -v k3s >/dev/null 2>&1; then
    echo "k3s är redan installerat ($(k3s --version | head -1)). Hoppar över installation."
else
    echo "Installerar k3s $K3S_VERSION..."
    curl -sfL https://get.k3s.io | \
        INSTALL_K3S_VERSION="$K3S_VERSION" \
        K3S_KUBECONFIG_MODE="644" \
        sh -s - server --disable traefik --tls-san skog-pi4.local
fi

echo "Väntar på att noden ska bli Ready..."
for _ in $(seq 1 30); do
    if k3s kubectl get node -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null | grep -q True; then
        echo "Noden är Ready."
        break
    fi
    sleep 2
done

k3s kubectl get node

echo
echo "Node-token för att senare joina Pi 3B+ till klustret (behövs i SKOG-010) ligger i:"
echo "  /var/lib/rancher/k3s/server/node-token  (kräver sudo för att läsa)"
