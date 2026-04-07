#!/bin/bash
set -Eeuo pipefail

REPO="https://github.com/Emadhabibnia1385/ConfigFlow.git"
BASE_DIR="/opt/configflow"
BASE_SERVICE="configflow"
DIR=""
SERVICE=""
INSTANCE_NUM=""
BOT_NAME=""

if [[ "${BASH_SOURCE[0]:-}" == /dev/fd/* ]] || [[ "${BASH_SOURCE[0]:-}" == /proc/*/fd/* ]]; then
  SCRIPT_DIR="$(pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

R='\033[31m'; G='\033[32m'; Y='\033[33m'; C='\033[36m'; M='\033[35m'; B='\033[1m'; W='\033[97m'; N='\033[0m'

# ─────────────────────────── header ───────────────────────────

header() {
  clear 2>/dev/null || true
  echo ""
  echo -e "${C}╔══════════════════════════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║${N}                                                                          ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M} ██████╗ ██████╗ ███╗   ██╗███████╗██╗ ██████╗ ███████╗██╗      ██╗${N}  ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M}██╔════╝██╔═══██╗████╗  ██║██╔════╝██║██╔════╝ ██╔════╝██║      ██║${N}  ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M}██║     ██║   ██║██╔██╗ ██║█████╗  ██║██║  ███╗█████╗  ██║  █╗  ██║${N}  ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M}██║     ██║   ██║██║╚██╗██║██╔══╝  ██║██║   ██║██╔══╝  ██║ ███╗ ██║${N}  ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M}╚██████╗╚██████╔╝██║ ╚████║██║     ██║╚██████╔╝██║     ╚███╔███╔╝ ${N}  ${C}║${N}"
  echo -e "${C}║${N}   ${B}${M} ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝ ╚═╝      ╚══╝╚══╝  ${N}  ${C}║${N}"
  echo -e "${C}║${N}                                                                          ${C}║${N}"
  echo -e "${C}║${N}          ${W}${B}⚡ ConfigFlow — Telegram Config Sales Bot ⚡${N}                  ${C}║${N}"
  echo -e "${C}║${N}                                                                          ${C}║${N}"
  echo -e "${C}╠══════════════════════════════════════════════════════════════════════════╣${N}"
  echo -e "${C}║${N}   ${B}${G}GitHub:${N}    github.com/Emadhabibnia1385/ConfigFlow                      ${C}║${N}"
  echo -e "${C}║${N}   ${B}${G}Developer:${N} t.me/EmadHabibnia                                          ${C}║${N}"
  echo -e "${C}║${N}   ${B}${G}Channel:${N}   @Emadhabibnia                                               ${C}║${N}"
  echo -e "${C}╚══════════════════════════════════════════════════════════════════════════╝${N}"
  echo ""
}

err()  { echo -e "${R}✗ $*${N}" >&2; exit 1; }
ok()   { echo -e "${G}✓ $*${N}"; }
info() { echo -e "${Y}➜ $*${N}"; }

on_error() { echo -e "${R}✗ Error on line ${BASH_LINENO[0]}${N}"; }
trap on_error ERR

check_root() {
  [[ $EUID -eq 0 ]] || err "Please run with sudo or as root"
}

ensure_safe_cwd() { cd / 2>/dev/null || true; }

install_prereqs() {
  info "Installing prerequisites..."
  apt-get update -y
  apt-get install -y git python3 python3-venv python3-pip curl
}

# ─────────────────────── helpers for name/time ───────────────────────────

get_bot_name() {
  local d="${BASE_DIR}-${1}"
  if [[ -f "$d/.bot_name" ]]; then
    cat "$d/.bot_name"
  else
    echo "Bot #${1}"
  fi
}

save_bot_name() {
  echo "$BOT_NAME" > "$DIR/.bot_name"
}

record_update_time() {
  date '+%Y-%m-%d %H:%M:%S' > "$DIR/.last_update"
}

get_last_update() {
  local d="${BASE_DIR}-${1}"
  if [[ -f "$d/.last_update" ]]; then
    cat "$d/.last_update"
  else
    echo "هرگز"
  fi
}

get_service_status() {
  local svc="${BASE_SERVICE}-${1}"
  if systemctl is-active "$svc" >/dev/null 2>&1; then
    echo -e "${G}🟢 آنلاین${N}"
  else
    echo -e "${R}🔴 آفلاین${N}"
  fi
}

get_autoupdate_status_label() {
  local svc="${BASE_SERVICE}-${1}-autoupdate"
  if systemctl is-active "${svc}.timer" >/dev/null 2>&1; then
    echo -e "${G}[روشن]${N}"
  else
    echo -e "${R}[خاموش]${N}"
  fi
}

# ─────────────────────────── repo / venv ───────────────────────────

clone_or_update_repo() {
  info "Downloading ConfigFlow..."
  mkdir -p "$DIR"
  if [[ -d "$DIR/.git" ]]; then
    info "Repository exists. Updating..."
    cd "$DIR"
    git fetch --all --prune
    git reset --hard origin/main
  else
    rm -rf "$DIR"
    mkdir -p "$DIR"
    git clone "$REPO" "$DIR"
    cd "$DIR"
  fi
  [[ -f "$DIR/main.py" ]]          || err "main.py not found after download."
  [[ -f "$DIR/requirements.txt" ]] || err "requirements.txt not found after download."
  record_update_time
}

setup_venv() {
  info "Setting up Python environment..."
  [[ -d "$DIR/venv" ]] || python3 -m venv "$DIR/venv"
  "$DIR/venv/bin/pip" install --upgrade pip wheel
  "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
}

# ─────────────────────────── configure ───────────────────────────

configure_env() {
  echo ""
  echo -e "${C}╔══════════════════════════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║${N}              ${B}${W}⚙️  پیکربندی ربات: ${BOT_NAME}${N}"
  echo -e "${C}╚══════════════════════════════════════════════════════════════════════════╝${N}"
  echo ""

  echo -e "${Y}📌 توکن ربات را از ${B}@BotFather${N}${Y} در تلگرام دریافت کنید.${N}"
  echo ""
  read -r -p "$(echo -e "${B}🔑 توکن Telegram Bot: ${N}")" INPUT_TOKEN
  INPUT_TOKEN="${INPUT_TOKEN// /}"
  [[ -n "$INPUT_TOKEN" ]]                      || err "توکن نمی‌تواند خالی باشد"
  [[ "$INPUT_TOKEN" =~ ^[0-9]+:.+$ ]]         || err "فرمت توکن نامعتبر است. مثال: 123456789:ABCdef..."

  echo ""
  echo -e "${Y}📌 برای دریافت Chat ID به ${B}@userinfobot${N}${Y} پیام دهید.${N}"
  echo ""
  read -r -p "$(echo -e "${B}👤 Chat ID ادمین (عددی): ${N}")" INPUT_ADMIN
  INPUT_ADMIN="${INPUT_ADMIN// /}"
  [[ "$INPUT_ADMIN" =~ ^-?[0-9]+$ ]] || err "Admin ID باید عددی باشد"

  echo ""
  read -r -p "$(echo -e "${B}📂 نام پایگاه داده [ConfigFlow.db]: ${N}")" INPUT_DB
  INPUT_DB="${INPUT_DB:-ConfigFlow.db}"

  cat > "$DIR/.env" << EOF
BOT_TOKEN=$INPUT_TOKEN
ADMIN_IDS=$INPUT_ADMIN
DB_NAME=$INPUT_DB
EOF
  chmod 600 "$DIR/.env"
  echo ""
  ok "پیکربندی در $DIR/.env ذخیره شد"
}

configure_iran_worker() {
  echo ""
  echo -e "${C}╔══════════════════════════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║${N}        ${B}${W}🇮🇷  پیکربندی Iran Worker (3x-ui) — ${BOT_NAME}${N}"
  echo -e "${C}╚══════════════════════════════════════════════════════════════════════════╝${N}"
  echo ""

  read -r -p "$(echo -e "${B}🌐 IP پنل (پیش‌فرض 127.0.0.1): ${N}")" INPUT_PANEL_IP
  INPUT_PANEL_IP="${INPUT_PANEL_IP:-127.0.0.1}"

  read -r -p "$(echo -e "${B}🔌 پورت پنل (پیش‌فرض 2053): ${N}")" INPUT_PANEL_PORT
  INPUT_PANEL_PORT="${INPUT_PANEL_PORT:-2053}"
  [[ "$INPUT_PANEL_PORT" =~ ^[0-9]+$ ]] || err "پورت باید عددی باشد"

  read -r -p "$(echo -e "${B}📄 مسیر (اختیاری، مثلاً /xui — Enter برای خالی): ${N}")" INPUT_PATCH
  INPUT_PATCH="${INPUT_PATCH:-}"

  read -r -p "$(echo -e "${B}👤 نام کاربری پنل: ${N}")" INPUT_PANEL_USER
  [[ -n "$INPUT_PANEL_USER" ]] || err "نام کاربری نمی‌تواند خالی باشد"

  read -r -s -p "$(echo -e "${B}🔑 رمز پنل: ${N}")" INPUT_PANEL_PASS
  echo ""
  [[ -n "$INPUT_PANEL_PASS" ]] || err "رمز نمی‌تواند خالی باشد"

  read -r -p "$(echo -e "${B}🆔 Inbound ID (پیش‌فرض 1): ${N}")" INPUT_INBOUND_ID
  INPUT_INBOUND_ID="${INPUT_INBOUND_ID:-1}"
  [[ "$INPUT_INBOUND_ID" =~ ^[0-9]+$ ]] || err "Inbound ID باید عددی باشد"

  read -r -p "$(echo -e "${B}🔐 Worker API Key (حداقل ۱۶ کاراکتر؛ Enter برای تولید خودکار): ${N}")" INPUT_WORKER_KEY
  if [[ -z "$INPUT_WORKER_KEY" ]]; then
    INPUT_WORKER_KEY=$(tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 32 || openssl rand -hex 16)
  fi
  [[ ${#INPUT_WORKER_KEY} -ge 16 ]] || err "API key باید حداقل ۱۶ کاراکتر باشد"

  read -r -p "$(echo -e "${B}🌍 Bot API URL (مثلاً http://foreign-server:8080): ${N}")" INPUT_API_URL
  [[ -n "$INPUT_API_URL" ]] || err "Bot API URL نمی‌تواند خالی باشد"

  read -r -p "$(echo -e "${B}⏱ فاصله بررسی (ثانیه، پیش‌فرض 10): ${N}")" INPUT_POLL
  INPUT_POLL="${INPUT_POLL:-10}"
  [[ "$INPUT_POLL" =~ ^[0-9]+$ ]] || err "بازه زمانی باید عددی باشد"

  cat > "$DIR/config.env" << ENVEOF
BOT_API_URL=$INPUT_API_URL
WORKER_API_KEY=$INPUT_WORKER_KEY
PANEL_IP=$INPUT_PANEL_IP
PANEL_PORT=$INPUT_PANEL_PORT
PANEL_PATCH=$INPUT_PATCH
PANEL_USERNAME=$INPUT_PANEL_USER
PANEL_PASSWORD=$INPUT_PANEL_PASS
INBOUND_ID=$INPUT_INBOUND_ID
POLL_INTERVAL=$INPUT_POLL
PROTOCOL=vless
ENVEOF
  chmod 600 "$DIR/config.env"
  echo ""
  ok "پیکربندی Worker در $DIR/config.env ذخیره شد"
  echo -e "${Y}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
  echo -e "${B}${W}   ⚠️  این API Key را برای پنل ادمین ربات نگه دارید:${N}"
  echo -e "   ${B}${G}WORKER_API_KEY = ${INPUT_WORKER_KEY}${N}"
  echo -e "${Y}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
  echo ""
  read -r -p "Enter را برای ادامه فشار دهید..."
}

# ─────────────────────────── systemd ───────────────────────────

create_systemd_service() {
  info "Creating systemd service for ${SERVICE}..."
  cat > "/etc/systemd/system/$SERVICE.service" << EOF
[Unit]
Description=ConfigFlow Telegram Bot — ${BOT_NAME}
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
EnvironmentFile=$DIR/.env
ExecStart=$DIR/venv/bin/python $DIR/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "$SERVICE" >/dev/null 2>&1 || true
}

create_worker_service() {
  [[ -f "$DIR/config.env" ]] || return 0
  info "Creating Iran Worker service for ${SERVICE}-worker..."
  cat > "/etc/systemd/system/${SERVICE}-worker.service" << EOF
[Unit]
Description=ConfigFlow Iran Worker — ${BOT_NAME}
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
EnvironmentFile=$DIR/config.env
ExecStart=$DIR/venv/bin/python $DIR/worker.py
Restart=always
RestartSec=10
StandardOutput=append:${DIR}/worker.log
StandardError=append:${DIR}/worker.log

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "${SERVICE}-worker" >/dev/null 2>&1 || true
  ok "سرویس Worker ایجاد شد: ${SERVICE}-worker"
}

start_service() {
  systemctl restart "$SERVICE"
  echo ""
  echo -e "${G}╔══════════════════════════════════════════════════════════════════════════╗${N}"
  echo -e "${G}║${N}        ${B}${G}✅  ${BOT_NAME} نصب و راه‌اندازی شد!${N}                          ${G}║${N}"
  echo -e "${G}╚══════════════════════════════════════════════════════════════════════════╝${N}"
  echo ""
  systemctl status "$SERVICE" --no-pager -l || true
}

# ─────────────────────────── auto-update ───────────────────────────

enable_auto_update() {
  ensure_safe_cwd
  [[ -d "$DIR/.git" ]] || err "ربات نصب نشده. ابتدا نصب کنید."

  local AUTOUPDATE_SCRIPT="$DIR/auto_update.sh"
  local AUTOUPDATE_SVC="${SERVICE}-autoupdate"

  info "Creating auto-update script..."
  cat > "$AUTOUPDATE_SCRIPT" << EOFSCRIPT
#!/bin/bash
cd "$DIR" || exit 1
git fetch --all --prune 2>/dev/null
LOCAL=\$(git rev-parse HEAD)
REMOTE=\$(git rev-parse origin/main)
if [[ "\$LOCAL" != "\$REMOTE" ]]; then
  echo "\$(date '+%Y-%m-%d %H:%M:%S') — Update found (\${LOCAL:0:7} → \${REMOTE:0:7}), updating..."
  git reset --hard origin/main
  "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt" -q
  date '+%Y-%m-%d %H:%M:%S' > "$DIR/.last_update"
  systemctl restart "$SERVICE"
  echo "\$(date '+%Y-%m-%d %H:%M:%S') — Updated and restarted $SERVICE"
else
  echo "\$(date '+%Y-%m-%d %H:%M:%S') — Already up to date (\${LOCAL:0:7})"
fi
EOFSCRIPT
  chmod +x "$AUTOUPDATE_SCRIPT"

  cat > "/etc/systemd/system/${AUTOUPDATE_SVC}.service" << EOF
[Unit]
Description=ConfigFlow Auto Update — ${BOT_NAME}
After=network.target

[Service]
Type=oneshot
ExecStart=$AUTOUPDATE_SCRIPT
StandardOutput=append:$DIR/autoupdate.log
StandardError=append:$DIR/autoupdate.log
EOF

  cat > "/etc/systemd/system/${AUTOUPDATE_SVC}.timer" << EOF
[Unit]
Description=ConfigFlow Auto Update Timer — ${BOT_NAME}

[Timer]
OnCalendar=minutely
Persistent=true

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable "${AUTOUPDATE_SVC}.timer" >/dev/null 2>&1
  systemctl start  "${AUTOUPDATE_SVC}.timer"
  echo ""
  ok "آپدیت خودکار برای ${BOT_NAME} فعال شد (هر دقیقه بررسی می‌شود)"
  echo -e "${Y}لاگ: $DIR/autoupdate.log${N}"
  echo ""
}

disable_auto_update() {
  ensure_safe_cwd
  local AUTOUPDATE_SVC="${SERVICE}-autoupdate"
  systemctl stop    "${AUTOUPDATE_SVC}.timer"   2>/dev/null || true
  systemctl disable "${AUTOUPDATE_SVC}.timer"   2>/dev/null || true
  systemctl stop    "${AUTOUPDATE_SVC}.service" 2>/dev/null || true
  rm -f "/etc/systemd/system/${AUTOUPDATE_SVC}.timer"
  rm -f "/etc/systemd/system/${AUTOUPDATE_SVC}.service"
  rm -f "$DIR/auto_update.sh"
  systemctl daemon-reload
  ok "آپدیت خودکار برای ${BOT_NAME} غیرفعال شد."
}

toggle_auto_update() {
  local AUTOUPDATE_SVC="${SERVICE}-autoupdate"
  if systemctl is-active "${AUTOUPDATE_SVC}.timer" >/dev/null 2>&1; then
    disable_auto_update
  else
    enable_auto_update
  fi
  read -r -p "Enter را فشار دهید..."
}

# ─────────────────────────── install / update / remove ───────────────────────────

install_bot() {
  ensure_safe_cwd
  install_prereqs
  clone_or_update_repo
  save_bot_name
  setup_venv
  configure_env
  create_systemd_service
  # auto-update by default
  enable_auto_update
  start_service
}

update_bot() {
  ensure_safe_cwd
  [[ -d "$DIR/.git" ]] || err "نصب نشده. ابتدا نصب کنید."
  info "Updating ${BOT_NAME}..."
  clone_or_update_repo
  setup_venv
  systemctl restart "$SERVICE"
  ok "بروزرسانی ${BOT_NAME} انجام شد!"
}

edit_config() {
  ensure_safe_cwd
  [[ -f "$DIR/.env" ]] || err "فایل تنظیمات پیدا نشد. ابتدا نصب کنید."
  nano "$DIR/.env"
  systemctl restart "$SERVICE"
  ok "تنظیمات ذخیره و ربات ری‌استارت شد!"
}

remove_bot() {
  ensure_safe_cwd
  read -r -p "آیا مطمئنید که می‌خواهید ${BOT_NAME} را حذف کنید؟ (yes/no): " confirm
  [[ "$confirm" == "yes" ]] || { info "لغو شد"; return; }

  for svc in "$SERVICE" "${SERVICE}-worker"; do
    systemctl stop    "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
    rm -f "/etc/systemd/system/${svc}.service"
  done
  systemctl stop    "${SERVICE}-autoupdate.timer"   2>/dev/null || true
  systemctl disable "${SERVICE}-autoupdate.timer"   2>/dev/null || true
  systemctl stop    "${SERVICE}-autoupdate.service" 2>/dev/null || true
  rm -f "/etc/systemd/system/${SERVICE}-autoupdate.timer"
  rm -f "/etc/systemd/system/${SERVICE}-autoupdate.service"
  systemctl daemon-reload
  rm -rf "$DIR"
  ok "${BOT_NAME} کاملاً حذف شد"
}

install_worker() {
  echo ""
  echo -e "${C}┌──────────────────────────────────────┐${N}"
  echo -e "${C}│${N}    ${B}${W}📦 منبع نصب Worker${N}               ${C}│${N}"
  echo -e "${C}├──────────────────────────────────────┤${N}"
  echo -e "${C}│${N}  ${B}${G}g)${N} 🌐 نصب از GitHub                 ${C}│${N}"
  echo -e "${C}│${N}  ${B}${M}l)${N} 📁 نصب از فایل‌های محلی          ${C}│${N}"
  echo -e "${C}└──────────────────────────────────────┘${N}"
  echo ""
  read -r -p "$(echo -e "${B}انتخاب [g/l]: ${N}")" src_choice
  case "${src_choice:-}" in
    g) _install_worker_github ;;
    l) _install_worker_local  ;;
    *) echo -e "${R}گزینه نامعتبر${N}"; return 1 ;;
  esac
}

_install_worker_github() {
  ensure_safe_cwd
  [[ -d "$DIR/.git" ]] || { install_prereqs; clone_or_update_repo; setup_venv; }
  [[ -d "$DIR/venv" ]] || setup_venv
  configure_iran_worker
  create_worker_service
  systemctl restart "${SERVICE}-worker"
  echo ""
  ok "Iran Worker برای ${BOT_NAME} نصب و راه‌اندازی شد!"
  systemctl status "${SERVICE}-worker" --no-pager -l || true
}

_install_worker_local() {
  ensure_safe_cwd
  info "نصب Iran Worker از فایل‌های محلی: $SCRIPT_DIR"
  local missing=0
  for f in worker.py requirements.txt; do
    [[ -f "$SCRIPT_DIR/$f" ]] || { echo -e "${R}✗ فایل گم است: $SCRIPT_DIR/$f${N}" >&2; missing=1; }
  done
  [[ $missing -eq 0 ]] || err "فایل‌های لازم را کنار install.sh قرار دهید"
  install_prereqs
  mkdir -p "$DIR"
  for f in worker.py requirements.txt; do
    cp -v "$SCRIPT_DIR/$f" "$DIR/$f"
    ok "Copied $f → $DIR/$f"
  done
  [[ -f "$SCRIPT_DIR/config.env.example" ]] && cp "$SCRIPT_DIR/config.env.example" "$DIR/config.env.example" || true
  setup_venv
  configure_iran_worker
  create_worker_service
  systemctl restart "${SERVICE}-worker"
  echo ""
  ok "Iran Worker برای ${BOT_NAME} نصب و راه‌اندازی شد!"
  systemctl status "${SERVICE}-worker" --no-pager -l || true
}

# ─────────────────────────── BULK OPERATIONS ───────────────────────────

all_instances() {
  local list=()
  for d in /opt/configflow-*/; do
    [[ -d "$d" ]] || continue
    local num; num="$(basename "$d" | sed 's/configflow-//')"
    [[ "$num" =~ ^[0-9]+$ ]] && list+=("$num")
  done
  echo "${list[@]:-}"
}

bulk_update_all() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    DIR="${BASE_DIR}-${num}"
    SERVICE="${BASE_SERVICE}-${num}"
    BOT_NAME="$(get_bot_name "$num")"
    echo ""
    echo -e "${C}━━━ بروزرسانی ${BOT_NAME} (شماره ${num}) ━━━${N}"
    [[ -d "$DIR/.git" ]] || { echo -e "${R}✗ نصب نشده، رد شد.${N}"; continue; }
    clone_or_update_repo
    setup_venv
    systemctl restart "$SERVICE" 2>/dev/null || true
    ok "${BOT_NAME} بروز شد"
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_enable_autoupdate() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    DIR="${BASE_DIR}-${num}"
    SERVICE="${BASE_SERVICE}-${num}"
    BOT_NAME="$(get_bot_name "$num")"
    echo ""
    echo -e "${C}━━━ فعال‌سازی آپدیت خودکار ${BOT_NAME} ━━━${N}"
    [[ -d "$DIR/.git" ]] || { echo -e "${R}✗ نصب نشده، رد شد.${N}"; continue; }
    enable_auto_update
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_disable_autoupdate() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    DIR="${BASE_DIR}-${num}"
    SERVICE="${BASE_SERVICE}-${num}"
    BOT_NAME="$(get_bot_name "$num")"
    echo ""
    echo -e "${C}━━━ غیرفعال‌سازی آپدیت خودکار ${BOT_NAME} ━━━${N}"
    disable_auto_update
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_restart_all() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    local svc="${BASE_SERVICE}-${num}"
    local name; name="$(get_bot_name "$num")"
    systemctl restart "$svc" 2>/dev/null && ok "ری‌استارت شد: ${name}" || echo -e "${R}✗ خطا: ${name}${N}"
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_start_all() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    local svc="${BASE_SERVICE}-${num}"
    local name; name="$(get_bot_name "$num")"
    systemctl start "$svc" 2>/dev/null && ok "روشن شد: ${name}" || echo -e "${R}✗ خطا: ${name}${N}"
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_stop_all() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  for num in $instances; do
    local svc="${BASE_SERVICE}-${num}"
    local name; name="$(get_bot_name "$num")"
    systemctl stop "$svc" 2>/dev/null && ok "خاموش شد: ${name}" || echo -e "${R}✗ خطا: ${name}${N}"
  done
  echo ""
  read -r -p "Enter را فشار دهید..."
}

bulk_remove_all() {
  local instances; instances="$(all_instances)"
  [[ -n "$instances" ]] || { echo -e "${Y}هیچ ربات نصب‌شده‌ای یافت نشد.${N}"; read -r -p "Enter..."; return; }
  echo -e "${R}⚠️  این عملیات تمام ربات‌ها را حذف خواهد کرد!${N}"
  read -r -p "برای تأیید «DELETE ALL» تایپ کنید: " confirm
  [[ "$confirm" == "DELETE ALL" ]] || { info "لغو شد"; read -r -p "Enter..."; return; }
  for num in $instances; do
    DIR="${BASE_DIR}-${num}"
    SERVICE="${BASE_SERVICE}-${num}"
    BOT_NAME="$(get_bot_name "$num")"
    echo ""
    echo -e "${C}━━━ حذف ${BOT_NAME} ━━━${N}"
    for svc in "$SERVICE" "${SERVICE}-worker"; do
      systemctl stop    "$svc" 2>/dev/null || true
      systemctl disable "$svc" 2>/dev/null || true
      rm -f "/etc/systemd/system/${svc}.service"
    done
    systemctl stop    "${SERVICE}-autoupdate.timer"   2>/dev/null || true
    systemctl disable "${SERVICE}-autoupdate.timer"   2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE}-autoupdate.timer"
    rm -f "/etc/systemd/system/${SERVICE}-autoupdate.service"
    rm -rf "$DIR"
    ok "${BOT_NAME} حذف شد"
  done
  systemctl daemon-reload
  echo ""
  read -r -p "Enter را فشار دهید..."
}

# ─────────────────────────── menus ───────────────────────────

list_instances_table() {
  local found=0
  echo -e "${C}┌────┬────────────────────────────┬───────────────┬──────────────────────┐${N}"
  echo -e "${C}│${N} ${B}${W}#${N}  ${C}│${N} ${B}${W}نام ربات${N}                    ${C}│${N} ${B}${W}وضعیت${N}         ${C}│${N} ${B}${W}آخرین آپدیت${N}          ${C}│${N}"
  echo -e "${C}├────┼────────────────────────────┼───────────────┼──────────────────────┤${N}"
  for d in /opt/configflow-*/; do
    [[ -d "$d" ]] || continue
    local num; num="$(basename "$d" | sed 's/configflow-//')"
    [[ "$num" =~ ^[0-9]+$ ]] || continue
    local name; name="$(get_bot_name "$num")"
    local svc="${BASE_SERVICE}-${num}"
    local status_raw status_str
    if systemctl is-active "$svc" >/dev/null 2>&1; then
      status_str="${G}🟢 آنلاین  ${N}"
    else
      status_str="${R}🔴 آفلاین${N}"
    fi
    local last; last="$(get_last_update "$num")"
    printf "${C}│${N} %-2s ${C}│${N} %-26s ${C}│${N} " "$num" "$name"
    echo -ne "$status_str"
    printf " ${C}│${N} %-20s ${C}│${N}\n" "$last"
    found=1
  done
  if [[ $found -eq 0 ]]; then
    echo -e "${C}│${N}               ${Y}هیچ ربات نصب‌شده‌ای یافت نشد${N}                              ${C}│${N}"
  fi
  echo -e "${C}└────┴────────────────────────────┴───────────────┴──────────────────────┘${N}"
  echo ""
}

show_global_menu() {
  echo -e "${C}┌──────────────────────────────────────────┐${N}"
  echo -e "${C}│${N}       ${B}${W}🌐 منوی اصلی — ConfigFlow${N}         ${C}│${N}"
  echo -e "${C}├──────────────────────────────────────────┤${N}"
  echo -e "${C}│${N}  ${B}${G}m)${N} 🤖 مدیریت یک ربات (انتخاب شماره)  ${C}│${N}"
  echo -e "${C}├──────────────────────────────────────────┤${N}"
  echo -e "${C}│${N}  ${B}${Y}1)${N} 🔄 بروزرسانی تمام ربات‌ها          ${C}│${N}"
  echo -e "${C}│${N}  ${B}${Y}2)${N} ⚡ روشن کردن آپدیت خودکار همه     ${C}│${N}"
  echo -e "${C}│${N}  ${B}${Y}3)${N} 🔕 خاموش کردن آپدیت خودکار همه   ${C}│${N}"
  echo -e "${C}│${N}  ${B}${Y}4)${N} 🔁 ری‌استارت تمام ربات‌ها           ${C}│${N}"
  echo -e "${C}│${N}  ${B}${Y}5)${N} ▶️  روشن کردن تمام ربات‌ها          ${C}│${N}"
  echo -e "${C}│${N}  ${B}${Y}6)${N} ⏹️  خاموش کردن تمام ربات‌ها         ${C}│${N}"
  echo -e "${C}│${N}  ${B}${R}7)${N} 🗑️  حذف تمام ربات‌ها                ${C}│${N}"
  echo -e "${C}├──────────────────────────────────────────┤${N}"
  echo -e "${C}│${N}  ${B}${R}0)${N} 🚪 خروج                            ${C}│${N}"
  echo -e "${C}└──────────────────────────────────────────┘${N}"
  echo ""
}

show_bot_header() {
  local au_status; au_status="$(get_autoupdate_status_label "$INSTANCE_NUM")"
  local bot_status; bot_status="$(get_service_status "$INSTANCE_NUM")"
  local last_upd; last_upd="$(get_last_update "$INSTANCE_NUM")"
  echo -e "${C}╔══════════════════════════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║${N}  🤖 ${B}${W}${BOT_NAME}${N}  (شماره ${INSTANCE_NUM})                                        ${C}║${N}"
  echo -e "${C}║${N}  وضعیت: $bot_status   │  آپدیت خودکار: $au_status   │  آخرین آپدیت: ${W}${last_upd}${N}  ${C}║${N}"
  echo -e "${C}╚══════════════════════════════════════════════════════════════════════════╝${N}"
  echo ""
}

show_bot_menu() {
  local au_label; au_label="$(get_autoupdate_status_label "$INSTANCE_NUM")"
  echo -e "${C}┌──────────────────────────────────────┐${N}"
  echo -e "${C}│${N}  ${B}${G}1)${N} 📦 نصب / نصب مجدد               ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}2)${N} 🔄 بروزرسانی از GitHub           ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}3)${N} ✏️  ویرایش تنظیمات (.env)         ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}4)${N} ▶️  روشن کردن                     ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}5)${N} ⏹️  خاموش کردن                    ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}6)${N} 🔁 ری‌استارت                      ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}7)${N} 📜 لاگ زنده                      ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}8)${N} 📊 وضعیت سرویس                   ${C}│${N}"
  echo -e "${C}│${N}  ${B}${G}9)${N} 🗑️  حذف این ربات                  ${C}│${N}"
  echo -e "${C}│${N}  ${B}${C}a)${N} ⚡ آپدیت خودکار: $au_label           ${C}│${N}"
  echo -e "${C}│${N}  ${B}${C}u)${N} 📋 لاگ آپدیت خودکار             ${C}│${N}"
  echo -e "${C}│${N}  ${B}${M}i)${N} 🇮🇷 نصب Iran Worker (3x-ui)      ${C}│${N}"
  echo -e "${C}│${N}  ${B}${M}w)${N} 📋 لاگ Worker                    ${C}│${N}"
  echo -e "${C}│${N}  ${B}${M}W)${N} 🔁 ری‌استارت Worker              ${C}│${N}"
  echo -e "${C}│${N}  ${B}${R}b)${N} 🔙 بازگشت به منوی اصلی          ${C}│${N}"
  echo -e "${C}└──────────────────────────────────────┘${N}"
  echo ""
}

# ─────────────────────────── instance selection ───────────────────────────

select_instance() {
  echo ""
  list_instances_table
  echo -e "${Y}📌 شماره ربات را وارد کنید (مثلاً 1، 2، 3 ...).${N}"
  echo -e "${Y}   هر شماره یک ربات مجزا با تنظیمات و دیتابیس خودش است.${N}"
  echo ""
  read -r -p "$(echo -e "${B}🔢 شماره ربات: ${N}")" INSTANCE_NUM
  INSTANCE_NUM="${INSTANCE_NUM// /}"
  [[ "$INSTANCE_NUM" =~ ^[0-9]+$ ]] || err "شماره باید عددی مثبت باشد (مثلاً 1، 2، 3)"
  [[ "$INSTANCE_NUM" -ge 1 ]]       || err "شماره باید >= 1 باشد"

  DIR="${BASE_DIR}-${INSTANCE_NUM}"
  SERVICE="${BASE_SERVICE}-${INSTANCE_NUM}"

  # If new instance → ask for a name
  if [[ ! -f "$DIR/.bot_name" ]]; then
    echo ""
    echo -e "${Y}📌 این ربات جدید است. یک نام برای شناسایی آسان وارد کنید.${N}"
    read -r -p "$(echo -e "${B}📛 نام ربات (مثلاً «ربات فروش اصلی»): ${N}")" INPUT_BOT_NAME
    INPUT_BOT_NAME="${INPUT_BOT_NAME:-Bot #${INSTANCE_NUM}}"
    BOT_NAME="$INPUT_BOT_NAME"
    mkdir -p "$DIR"
    save_bot_name
  else
    BOT_NAME="$(get_bot_name "$INSTANCE_NUM")"
  fi

  echo ""
  ok "ربات انتخاب شد: ${B}${BOT_NAME}${N}  (پوشه: $DIR  سرویس: $SERVICE)"
  echo ""
}

# ─────────────────────────── main loops ───────────────────────────

bot_loop() {
  while true; do
    header
    show_bot_header
    show_bot_menu

    read -r -p "$(echo -e "${C}${BOT_NAME}${N} ${B}➜${N} گزینه ${W}[0-9/a/u/i/w/W/b]${N}: ")" choice

    case "${choice:-}" in
      1) install_bot; read -r -p "Enter...";;
      2) update_bot;  read -r -p "Enter...";;
      3) edit_config ;;
      4) systemctl start   "$SERVICE" 2>/dev/null && ok "روشن شد: ${BOT_NAME}";   read -r -p "Enter...";;
      5) systemctl stop    "$SERVICE" 2>/dev/null && ok "خاموش شد: ${BOT_NAME}";  read -r -p "Enter...";;
      6) systemctl restart "$SERVICE" 2>/dev/null && ok "ری‌استارت شد: ${BOT_NAME}"; read -r -p "Enter...";;
      7) echo -e "${Y}Ctrl+C برای خروج از لاگ${N}"; sleep 1; journalctl -u "$SERVICE" -f;;
      8) systemctl status "$SERVICE" --no-pager -l; read -r -p "Enter...";;
      9) remove_bot; read -r -p "Enter..."; return;;
      a) toggle_auto_update ;;
      u) echo -e "${Y}Ctrl+C برای خروج از لاگ${N}"; sleep 1
         tail -f "$DIR/autoupdate.log" 2>/dev/null || echo -e "${R}فایل لاگ یافت نشد.${N}"
         read -r -p "Enter...";;
      i) install_worker; read -r -p "Enter...";;
      w) echo -e "${Y}Ctrl+C برای خروج از لاگ${N}"; sleep 1; journalctl -u "${SERVICE}-worker" -f;;
      W) systemctl restart "${SERVICE}-worker" 2>/dev/null && ok "Worker ری‌استارت شد"; read -r -p "Enter...";;
      b) return;;
      *) echo -e "${R}گزینه نامعتبر${N}"; sleep 1;;
    esac
  done
}

main() {
  [[ -t 0 ]] || exec < /dev/tty
  check_root
  ensure_safe_cwd

  while true; do
    header
    list_instances_table
    show_global_menu

    read -r -p "$(echo -e "${C}ConfigFlow${N} ${B}➜${N} گزینه ${W}[m/1-7/0]${N}: ")" choice

    case "${choice:-}" in
      m)
        select_instance
        bot_loop
        ;;
      1) header; bulk_update_all ;;
      2) header; bulk_enable_autoupdate ;;
      3) header; bulk_disable_autoupdate ;;
      4) header; bulk_restart_all ;;
      5) header; bulk_start_all ;;
      6) header; bulk_stop_all ;;
      7) header; bulk_remove_all ;;
      0) echo "خداحافظ!"; exit 0;;
      *) echo -e "${R}گزینه نامعتبر${N}"; sleep 1;;
    esac
  done
}

main
