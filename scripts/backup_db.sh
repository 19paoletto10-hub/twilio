#!/bin/bash
# =============================================================================
# backup_db.sh - Automatyczny backup bazy SQLite z kontenera Docker
# =============================================================================
#
# OPIS:
#   Skrypt tworzy kopię zapasową bazy danych SQLite używanej przez aplikację
#   Twilio Chat App. Obsługuje zarówno kontenery Docker jak i lokalne pliki.
#
# UŻYCIE:
#   ./scripts/backup_db.sh              # Backup do katalogu ./backup/
#   ./scripts/backup_db.sh /custom/path # Backup do wskazanego katalogu
#   ./scripts/backup_db.sh --help       # Pokaż pomoc
#
# PRZYKŁADY:
#   # Standardowy backup
#   ./scripts/backup_db.sh
#
#   # Backup do katalogu /mnt/backups
#   ./scripts/backup_db.sh /mnt/backups
#
#   # Backup z cron (codziennie o 2:00)
#   0 2 * * * cd /path/to/twilio && ./scripts/backup_db.sh >> /var/log/twilio-backup.log 2>&1
#
# WYMAGANIA:
#   - Docker z uruchomionym kontenerem aplikacji, LUB
#   - Bezpośredni dostęp do pliku data/app.db
#   - Opcjonalnie: sqlite3 (do weryfikacji integralności)
#
# KONFIGURACJA:
#   Zmienne środowiskowe (opcjonalne):
#   - BACKUP_KEEP_DAYS: Ile dni trzymać backupy (domyślnie: 7)
#   - DB_CONTAINER_NAME: Wzorzec nazwy kontenera (domyślnie: 'twilio.*web')
#
# AUTOR:
#   Twilio Chat App Team
#
# =============================================================================

set -euo pipefail

# =============================================================================
# KONFIGURACJA
# =============================================================================

# Katalog docelowy backupu (domyślnie ./backup lub pierwszy argument)
BACKUP_DIR="${1:-./backup}"

# Ile dni przechowywać stare backupy (0 = nie usuwaj)
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"

# Wzorzec nazwy kontenera Docker
CONTAINER_PATTERN="${DB_CONTAINER_NAME:-twilio.*web}"

# Nazwa pliku bazy danych
DB_NAME="app.db"

# Ścieżka do bazy w kontenerze
DB_PATH_CONTAINER="/app/data/${DB_NAME}"

# Ścieżka do bazy lokalnie (gdy volume zamontowany)
DB_PATH_LOCAL="data/${DB_NAME}"

# Timestamp dla nazwy pliku
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Pełna ścieżka do pliku backupu
BACKUP_FILE="${BACKUP_DIR}/app_${TIMESTAMP}.db"

# =============================================================================
# KOLORY I FORMATOWANIE
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# =============================================================================
# FUNKCJE POMOCNICZE
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

show_help() {
    cat << 'EOF'
┌─────────────────────────────────────────────────────────────────┐
│                    BACKUP_DB.SH - POMOC                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  UŻYCIE:                                                        │
│    ./scripts/backup_db.sh [KATALOG_BACKUPU]                     │
│                                                                 │
│  ARGUMENTY:                                                     │
│    KATALOG_BACKUPU   Ścieżka do katalogu backupu                │
│                      (domyślnie: ./backup)                      │
│                                                                 │
│  OPCJE:                                                         │
│    --help, -h        Pokaż tę pomoc                             │
│    --dry-run         Tylko sprawdź, nie twórz backupu           │
│    --list            Pokaż istniejące backupy                   │
│    --restore FILE    Przywróć backup z pliku                    │
│                                                                 │
│  ZMIENNE ŚRODOWISKOWE:                                          │
│    BACKUP_KEEP_DAYS  Ile dni trzymać backupy (domyślnie: 7)     │
│                                                                 │
│  PRZYKŁADY:                                                     │
│    ./scripts/backup_db.sh                                       │
│    ./scripts/backup_db.sh /mnt/nas/backups                      │
│    BACKUP_KEEP_DAYS=30 ./scripts/backup_db.sh                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
EOF
}

list_backups() {
    echo -e "${BLUE}${BOLD}Istniejące backupy w ${BACKUP_DIR}:${NC}"
    echo ""
    if [ -d "$BACKUP_DIR" ] && ls "$BACKUP_DIR"/app_*.db 1> /dev/null 2>&1; then
        ls -lh "$BACKUP_DIR"/app_*.db | awk '{print "  " $9 " (" $5 ", " $6 " " $7 " " $8 ")"}'
        echo ""
        TOTAL=$(ls "$BACKUP_DIR"/app_*.db | wc -l)
        echo -e "  ${BOLD}Łącznie: ${TOTAL} backup(ów)${NC}"
    else
        echo "  (brak backupów)"
    fi
}

restore_backup() {
    local RESTORE_FILE="$1"
    
    if [ ! -f "$RESTORE_FILE" ]; then
        log_error "Plik nie istnieje: $RESTORE_FILE"
        exit 1
    fi
    
    log_warn "UWAGA: Ta operacja nadpisze obecną bazę danych!"
    read -p "Czy kontynuować? (tak/nie): " CONFIRM
    
    if [ "$CONFIRM" != "tak" ]; then
        log_info "Anulowano."
        exit 0
    fi
    
    # Zatrzymaj kontenery jeśli działają
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        log_info "Zatrzymuję kontenery..."
        docker compose down
    fi
    
    # Stwórz backup obecnej bazy przed nadpisaniem
    if [ -f "$DB_PATH_LOCAL" ]; then
        BEFORE_RESTORE="${BACKUP_DIR}/app_before_restore_${TIMESTAMP}.db"
        cp "$DB_PATH_LOCAL" "$BEFORE_RESTORE"
        log_info "Backup przed restore: $BEFORE_RESTORE"
    fi
    
    # Przywróć
    cp "$RESTORE_FILE" "$DB_PATH_LOCAL"
    log_success "Przywrócono bazę z: $RESTORE_FILE"
    
    log_info "Uruchom aplikację: docker compose up -d"
}

# =============================================================================
# PARSOWANIE ARGUMENTÓW
# =============================================================================

case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --list)
        list_backups
        exit 0
        ;;
    --restore)
        if [ -z "${2:-}" ]; then
            log_error "Podaj ścieżkę do pliku backupu"
            exit 1
        fi
        restore_backup "$2"
        exit 0
        ;;
    --dry-run)
        DRY_RUN=true
        shift
        BACKUP_DIR="${1:-./backup}"
        ;;
esac

# =============================================================================
# GŁÓWNA LOGIKA
# =============================================================================

log_info "=== Backup bazy danych Twilio Chat App ==="
log_info "Katalog docelowy: ${BACKUP_DIR}"

# Utwórz katalog backupu jeśli nie istnieje
mkdir -p "$BACKUP_DIR"

# Określ źródło bazy danych
SOURCE=""
SOURCE_TYPE=""

# Opcja 1: Baza dostępna lokalnie (volume zamontowany)
if [ -f "$DB_PATH_LOCAL" ]; then
    SOURCE="$DB_PATH_LOCAL"
    SOURCE_TYPE="local"
    log_info "Znaleziono bazę lokalnie: ${SOURCE}"
fi

# Opcja 2: Baza w kontenerze Docker
if [ -z "$SOURCE" ]; then
    if command -v docker &> /dev/null; then
        CONTAINER=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "$CONTAINER_PATTERN" | head -1 || true)
        
        if [ -n "$CONTAINER" ]; then
            SOURCE="${CONTAINER}:${DB_PATH_CONTAINER}"
            SOURCE_TYPE="docker"
            log_info "Znaleziono kontener Docker: ${CONTAINER}"
        fi
    fi
fi

# Brak źródła
if [ -z "$SOURCE" ]; then
    log_error "Nie znaleziono bazy danych!"
    log_error ""
    log_error "Upewnij się, że:"
    log_error "  1. Kontener Docker jest uruchomiony:"
    log_error "     docker compose up -d"
    log_error ""
    log_error "  2. LUB plik data/app.db istnieje lokalnie"
    log_error ""
    log_error "Wzorzec kontenera: '${CONTAINER_PATTERN}'"
    log_error "Ścieżka lokalna: '${DB_PATH_LOCAL}'"
    exit 1
fi

# Tryb dry-run
if [ "${DRY_RUN:-false}" = true ]; then
    log_info "[DRY-RUN] Backup zostałby utworzony jako: ${BACKUP_FILE}"
    log_info "[DRY-RUN] Źródło: ${SOURCE} (${SOURCE_TYPE})"
    exit 0
fi

# =============================================================================
# WYKONANIE BACKUPU
# =============================================================================

log_info "Tworzenie backupu..."

case "$SOURCE_TYPE" in
    local)
        # Użyj SQLite .backup dla spójności (jeśli dostępny)
        if command -v sqlite3 &> /dev/null; then
            sqlite3 "$SOURCE" ".backup '${BACKUP_FILE}'"
        else
            cp "$SOURCE" "$BACKUP_FILE"
        fi
        ;;
    docker)
        docker cp "$SOURCE" "$BACKUP_FILE"
        ;;
esac

# =============================================================================
# WERYFIKACJA
# =============================================================================

if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup nie został utworzony!"
    exit 1
fi

# Rozmiar pliku
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_success "Backup utworzony: ${BACKUP_FILE} (${SIZE})"

# Weryfikacja integralności SQLite
if command -v sqlite3 &> /dev/null; then
    log_info "Weryfikacja integralności..."
    
    INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>&1)
    
    if echo "$INTEGRITY" | grep -q "^ok$"; then
        log_success "Integralność bazy: OK"
    else
        log_warn "Integralność bazy: PROBLEM"
        log_warn "Szczegóły: ${INTEGRITY}"
    fi
    
    # Statystyki
    TABLES=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "?")
    MESSAGES=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM messages;" 2>/dev/null || echo "?")
    
    log_info "Statystyki: ${TABLES} tabel, ${MESSAGES} wiadomości"
else
    log_warn "sqlite3 nie zainstalowane - pominięto weryfikację integralności"
fi

# =============================================================================
# ROTACJA STARYCH BACKUPÓW
# =============================================================================

if [ "$KEEP_DAYS" -gt 0 ]; then
    log_info "Usuwanie backupów starszych niż ${KEEP_DAYS} dni..."
    
    DELETED=$(find "$BACKUP_DIR" -name "app_*.db" -mtime +$KEEP_DAYS -delete -print 2>/dev/null | wc -l || echo "0")
    
    if [ "$DELETED" -gt 0 ]; then
        log_info "Usunięto ${DELETED} starych backupów"
    fi
fi

# =============================================================================
# PODSUMOWANIE
# =============================================================================

echo ""
log_info "=== Podsumowanie ==="
echo ""
echo -e "  ${BOLD}Backup:${NC}     ${BACKUP_FILE}"
echo -e "  ${BOLD}Rozmiar:${NC}    ${SIZE}"
echo -e "  ${BOLD}Źródło:${NC}     ${SOURCE_TYPE}"
echo ""

# Lista ostatnich backupów
echo -e "  ${BOLD}Ostatnie backupy:${NC}"
ls -lht "$BACKUP_DIR"/app_*.db 2>/dev/null | head -5 | awk '{print "    " $9 " (" $5 ")"}'

echo ""
log_success "=== Backup zakończony pomyślnie ==="
