#!/usr/bin/env bash
# =============================================================================
# setup.sh — Raspberry Pi 3 sécurisé pour enfants (≈10 ans)
# =============================================================================
# Usage (en tant que root) :
#   sudo bash setup.sh [nom_utilisateur] [mot_de_passe]
#
# Exemple :
#   sudo bash setup.sh enfants MonMotDePasse123
#
# Ce script :
#   1. Crée un compte utilisateur restreint pour les enfants
#   2. Configure un DNS familial (Cloudflare Family 1.1.1.3)
#   3. Bloque les sites adultes via /etc/hosts
#   4. Sécurise Chromium (SafeSearch forcé, mode incognito désactivé)
#   5. Installe des limites de temps d'écran via cron
#   6. Restreint l'accès au bureau et aux paramètres système
# =============================================================================

set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Vérifications préalables ──────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Ce script doit être exécuté en tant que root (sudo)."

KIDS_USER="${1:-enfants}"
KIDS_PASS="${2:-}"

if [[ -z "$KIDS_PASS" ]]; then
    read -rsp "Mot de passe pour le compte '${KIDS_USER}' : " KIDS_PASS
    echo
    [[ -z "$KIDS_PASS" ]] && error "Le mot de passe ne peut pas être vide."
fi

# ── Heures d'accès autorisées (modifiables) ───────────────────────────────────
# Plage horaire autorisée pour la semaine (lundi–vendredi)
WEEKDAY_START="14:00"   # 14h
WEEKDAY_END="18:00"     # 18h
# Plage horaire autorisée pour le week-end (samedi–dimanche)
WEEKEND_START="09:00"   # 9h
WEEKEND_END="19:00"     # 19h
# Durée maximale de session (minutes)
MAX_SESSION_MINUTES=120

# =============================================================================
# 1. CRÉATION DU COMPTE ENFANTS
# =============================================================================
info "=== 1/7 Création du compte '${KIDS_USER}' ==="

if id "$KIDS_USER" &>/dev/null; then
    warn "L'utilisateur '${KIDS_USER}' existe déjà. Mise à jour du mot de passe."
else
    useradd -m -s /bin/bash -c "Compte Enfants" "$KIDS_USER"
    info "Utilisateur '${KIDS_USER}' créé."
fi

echo "${KIDS_USER}:${KIDS_PASS}" | chpasswd

# Bloquer l'accès sudo
if getent group sudo | grep -qw "$KIDS_USER"; then
    gpasswd -d "$KIDS_USER" sudo || true
fi

# Ajouter au groupe audio/video uniquement (pas adm, dialout, etc.)
usermod -G audio,video,plugdev,netdev "$KIDS_USER" 2>/dev/null || true

info "Compte '${KIDS_USER}' configuré (sans privilèges sudo)."

# =============================================================================
# 2. DNS FAMILIAL
# =============================================================================
info "=== 2/7 Configuration du DNS familial (Cloudflare Family) ==="

# Désactiver le DNS automatique du DHCP et forcer Cloudflare Family
RESOLV="/etc/resolv.conf"
# Supprimer le lien symbolique éventuel de systemd-resolved
if [[ -L "$RESOLV" ]]; then
    rm -f "$RESOLV"
fi

cat > "$RESOLV" <<'EOF'
# DNS Cloudflare Family (bloque malwares + contenus adultes)
nameserver 1.1.1.3
nameserver 1.0.0.3
# Fallback OpenDNS FamilyShield
nameserver 208.67.222.123
nameserver 208.67.220.123
EOF

# Protéger le fichier contre la réécriture par dhcpcd
chattr +i "$RESOLV" 2>/dev/null || warn "Impossible de verrouiller /etc/resolv.conf (chattr non disponible)."

# Si dhcpcd est utilisé, lui dire de ne pas écraser le DNS
DHCPCD_CONF="/etc/dhcpcd.conf"
if [[ -f "$DHCPCD_CONF" ]] && ! grep -q "nohook resolv.conf" "$DHCPCD_CONF"; then
    echo -e "\n# Ne pas écraser le DNS familial\nnohook resolv.conf" >> "$DHCPCD_CONF"
fi

info "DNS familial configuré."

# =============================================================================
# 3. BLOCAGE HOSTS (couche supplémentaire)
# =============================================================================
info "=== 3/7 Mise à jour de /etc/hosts ==="

HOSTS_MARKER="# ---- KIDS BLOCK BEGIN ----"
if ! grep -q "$HOSTS_MARKER" /etc/hosts; then
    cat >> /etc/hosts <<'HOSTS'

# ---- KIDS BLOCK BEGIN ----
# Quelques domaines bloqués en complément du DNS familial
127.0.0.1  pornhub.com www.pornhub.com
127.0.0.1  xvideos.com www.xvideos.com
127.0.0.1  xnxx.com www.xnxx.com
127.0.0.1  4chan.org www.4chan.org
127.0.0.1  reddit.com www.reddit.com old.reddit.com
127.0.0.1  tiktok.com www.tiktok.com
# ---- KIDS BLOCK END ----
HOSTS
fi

info "/etc/hosts mis à jour."

# =============================================================================
# 4. CHROMIUM — POLITIQUES DE SÉCURITÉ
# =============================================================================
info "=== 4/7 Configuration de Chromium (SafeSearch, contrôles parentaux) ==="

POLICY_DIR="/etc/chromium/policies/managed"
mkdir -p "$POLICY_DIR"

cat > "${POLICY_DIR}/kids_policy.json" <<'JSON'
{
  "IncognitoModeAvailability": 1,
  "BrowserSignin": 0,
  "SyncDisabled": true,
  "PasswordManagerEnabled": false,
  "SafeBrowsingEnabled": true,
  "SafeBrowsingExtendedReportingEnabled": false,
  "ForceGoogleSafeSearch": true,
  "ForceYouTubeRestrict": 2,
  "AllowDeletingBrowserHistory": false,
  "PrintingEnabled": true,
  "DownloadRestrictions": 3,
  "DefaultPopupsSetting": 2,
  "DefaultNotificationsSetting": 2,
  "DefaultGeolocationSetting": 2,
  "DefaultCameraAccessSetting": 2,
  "DefaultMicrophoneAccessSetting": 2,
  "AutoplayAllowed": false,
  "BookmarkBarEnabled": true,
  "ShowHomeButton": true,
  "HomepageLocation": "https://www.google.fr",
  "HomepageIsNewTabPage": false,
  "NewTabPageLocation": "https://www.google.fr",
  "URLBlocklist": [
    "chrome://settings",
    "chrome://extensions",
    "chrome://flags",
    "chrome://os-settings"
  ],
  "ExtensionInstallBlocklist": ["*"],
  "ExtensionInstallAllowlist": []
}
JSON

info "Politiques Chromium appliquées."

# =============================================================================
# 5. LIMITES DE TEMPS — SCRIPT DE DÉCONNEXION AUTOMATIQUE
# =============================================================================
info "=== 5/7 Installation des limites de temps d'écran ==="

SESSION_GUARD="/usr/local/bin/kids-session-guard.sh"
cat > "$SESSION_GUARD" <<GUARD
#!/usr/bin/env bash
# kids-session-guard.sh
# Vérifie si l'utilisateur enfants est connecté en dehors des heures autorisées
# ou a dépassé la durée maximale de session, et le déconnecte si nécessaire.

KIDS_USER="${KIDS_USER}"
MAX_MINUTES=${MAX_SESSION_MINUTES}

# Heures autorisées : sem. 14-18, we 9-19
DOW=\$(date +%u)   # 1=lundi … 7=dimanche
HOUR=\$(date +%H)
MIN=\$(date +%M)
NOW_MINUTES=\$(( HOUR * 60 + MIN ))

if [[ \$DOW -le 5 ]]; then
    START_M=\$(( 14 * 60 ))   # 14:00
    END_M=\$(( 18 * 60 ))     # 18:00
else
    START_M=\$(( 9 * 60 ))    # 09:00
    END_M=\$(( 19 * 60 ))     # 19:00
fi

# Vérifier si l'utilisateur est connecté
if ! who | grep -q "^\${KIDS_USER} "; then
    exit 0
fi

KICK=false
REASON=""

# Hors plage horaire ?
if [[ \$NOW_MINUTES -lt \$START_M || \$NOW_MINUTES -ge \$END_M ]]; then
    KICK=true
    REASON="hors des heures autorisées"
fi

# Durée de session dépassée ?
LOGIN_EPOCH=\$(who -s | awk -v u="\$KIDS_USER" '\$1==u{print \$3" "\$4}' | head -1)
if [[ -n "\$LOGIN_EPOCH" ]]; then
    LOGIN_TS=\$(date -d "\$LOGIN_EPOCH" +%s 2>/dev/null || echo 0)
    NOW_TS=\$(date +%s)
    ELAPSED_MIN=\$(( (NOW_TS - LOGIN_TS) / 60 ))
    if [[ \$ELAPSED_MIN -ge \$MAX_MINUTES ]]; then
        KICK=true
        REASON="durée maximale de \${MAX_MINUTES} min atteinte"
    fi
fi

if \$KICK; then
    # Afficher un avertissement avant déconnexion (si display disponible)
    export DISPLAY=:0
    XUSER=\$(who | awk -v u="\$KIDS_USER" '\$1==u{print \$5}' | tr -d '()' | head -1)
    if [[ -n "\$XUSER" ]]; then
        su - "\$KIDS_USER" -c "DISPLAY=\${XUSER} notify-send -u critical 'Temps écran' 'Session terminée : \${REASON}. Au revoir !' 2>/dev/null || true"
        sleep 10
    fi
    # Tuer la session
    pkill -TERM -u "\$KIDS_USER" || true
    sleep 3
    pkill -KILL -u "\$KIDS_USER" || true
    logger "kids-session-guard: déconnexion de \${KIDS_USER} — \${REASON}"
fi
GUARD

chmod +x "$SESSION_GUARD"

# Installer le cron (toutes les 5 minutes)
CRON_FILE="/etc/cron.d/kids-session-guard"
cat > "$CRON_FILE" <<CRON
# Vérification de la session enfants toutes les 5 minutes
*/5 * * * * root ${SESSION_GUARD} >> /var/log/kids-session.log 2>&1
CRON

info "Garde-fou de session installé (vérification toutes les 5 min)."

# =============================================================================
# 6. RESTRICTIONS BUREAU (LXDE / PIXEL)
# =============================================================================
info "=== 6/7 Restrictions du bureau LXDE ==="

KIDS_HOME="/home/${KIDS_USER}"
KIDS_CONF="${KIDS_HOME}/.config"
mkdir -p "${KIDS_CONF}/lxsession/LXDE-pi"
mkdir -p "${KIDS_CONF}/lxpanel/LXDE-pi/panels"

# Désactiver le gestionnaire de fichiers sur le bureau
cat > "${KIDS_CONF}/lxsession/LXDE-pi/autostart" <<'AUTOSTART'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xscreensaver -no-splash
# NE PAS démarrer le terminal, le gestionnaire de fichiers, etc.
AUTOSTART

# Verrouillage d'écran après 10 minutes d'inactivité
mkdir -p "${KIDS_CONF}/xscreensaver"
cat > "${KIDS_HOME}/.xscreensaver" <<'XSCR'
mode:         blank
timeout:      0:10:00
lock:         True
lockTimeout:  0:00:30
XSCR

# Restreindre le menu clic-droit sur le bureau
cat > "${KIDS_CONF}/libfm/libfm.conf" <<'LIBFM'
[config]
show_hidden=0
LIBFM

# Propriétaire correct
chown -R "${KIDS_USER}:${KIDS_USER}" "${KIDS_HOME}/.config" "${KIDS_HOME}/.xscreensaver" 2>/dev/null || true

info "Bureau LXDE restreint."

# =============================================================================
# 7. RACCOURCIS & RÉSUMÉ
# =============================================================================
info "=== 7/7 Finalisation ==="

# Créer un fichier de statut lisible par les parents
cat > "/home/${KIDS_USER}/INFOS_PARENTS.txt" <<INFO
=== Configuration du compte enfants ===

Nom du compte  : ${KIDS_USER}
Créé le        : $(date)

Heures autorisées :
  Lun–Ven : ${WEEKDAY_START} → ${WEEKDAY_END}
  Sam–Dim : ${WEEKEND_START} → ${WEEKEND_END}
  Durée max / session : ${MAX_SESSION_MINUTES} minutes

DNS familial : Cloudflare Family (1.1.1.3 + 1.0.0.3)
               OpenDNS FamilyShield (208.67.222.123)

Chromium :
  - SafeSearch Google forcé
  - YouTube en mode restreint (niveau 2)
  - Mode incognito désactivé
  - Téléchargements bloqués
  - Paramètres Chromium inaccessibles

Verrouillage écran : après 10 min d'inactivité

Pour modifier les horaires, éditez :
  ${SESSION_GUARD}
Pour modifier les politiques Chromium :
  ${POLICY_DIR}/kids_policy.json

Journal de session : /var/log/kids-session.log
INFO

chown "${KIDS_USER}:${KIDS_USER}" "/home/${KIDS_USER}/INFOS_PARENTS.txt"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓  Configuration terminée avec succès !            ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Compte    : ${KIDS_USER}                                      ║${NC}"
echo -e "${GREEN}║  Sem.      : ${WEEKDAY_START} – ${WEEKDAY_END}  (max ${MAX_SESSION_MINUTES} min)           ║${NC}"
echo -e "${GREEN}║  Week-end  : ${WEEKEND_START} – ${WEEKEND_END}  (max ${MAX_SESSION_MINUTES} min)           ║${NC}"
echo -e "${GREEN}║  DNS       : Cloudflare Family 1.1.1.3               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
warn "Redémarrez le Raspberry Pi pour appliquer tous les changements : sudo reboot"
