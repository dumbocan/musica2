#!/bin/bash
#
# setup_ollama.sh - Instalación automática de Ollama para audio2
#
# Este script instala Ollama y descarga el modelo Llama-3.2-3B
# para el sistema de inteligencia musical de audio2.
#
# Uso: bash setup_ollama.sh
#

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes con color
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Función para detectar el sistema operativo
detect_os() {
    print_info "Detectando sistema operativo..."

    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS_ID=$ID
        OS_VERSION_ID=$VERSION_ID
    elif [[ "$(uname)" == "Darwin" ]]; then
        OS_ID="macos"
    elif [[ "$(uname)" == "Linux" ]]; then
        # Check if it's WSL
        if grep -qi "microsoft" /proc/version 2>/dev/null; then
            OS_ID="wsl"
        else
            OS_ID="linux"
        fi
    else
        OS_ID="unknown"
    fi

    # Normalize
    case "$OS_ID" in
        ubuntu|debian|linuxmint|pop)
            OS_FAMILY="debian"
            ;;
        fedora|rhel|centos|rocky|alma)
            OS_FAMILY="rhel"
            ;;
        arch|manjaro)
            OS_FAMILY="arch"
            ;;
        macos)
            OS_FAMILY="macos"
            ;;
        wsl)
            OS_FAMILY="wsl"
            ;;
        *)
            OS_FAMILY="linux"
            ;;
    esac

    print_success "Sistema detectado: $OS_ID ($OS_FAMILY)"
}

# Función para verificar si Ollama está instalado
check_ollama_installed() {
    if command -v ollama &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Función para verificar si Ollama está corriendo
check_ollama_running() {
    if curl -s http://localhost:11434/api/version &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Función para instalar Ollama en Debian/Ubuntu
install_ollama_debian() {
    print_info "Instalando Ollama en Debian/Ubuntu..."

    # Instalar dependencias
    sudo apt-get update
    sudo apt-get install -y curl ca-certificates

    # Instalar Ollama
    curl -fsSL https://ollama.com/install.sh | sh

    print_success "Ollama instalado correctamente"
}

# Función para instalar Ollama en RHEL/Fedora/CentOS
install_ollama_rhel() {
    print_info "Instalando Ollama en RHEL/Fedora/CentOS..."

    # Instalar dependencias
    sudo dnf install -y curl ca-certificates

    # Instalar Ollama
    curl -fsSL https://ollama.com/install.sh | sh

    print_success "Ollama instalado correctamente"
}

# Función para instalar Ollama en Arch Linux
install_ollama_arch() {
    print_info "Instalando Ollama en Arch Linux..."

    # Usar yay o pacman
    if command -v yay &> /dev/null; then
        yay -S ollama --noconfirm
    elif command -v pacman &> /dev/null; then
        # Instalar desde AUR (simplificado)
        cd /tmp
        git clone https://aur.archlinux.org/ollama.git
        cd ollama
        makepkg -si --noconfirm
        cd -
        rm -rf /tmp/ollama
    else
        # Usar el script oficial
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    print_success "Ollama instalado correctamente"
}

# Función para instalar Ollama en macOS
install_ollama_macos() {
    print_info "Instalando Ollama en macOS..."

    # Verificar si Homebrew está instalado
    if ! command -v brew &> /dev/null; then
        print_warning "Homebrew no está instalado. Por favor instala Homebrew primero:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 1
    fi

    brew install ollama

    print_success "Ollama instalado correctamente"
}

# Función para instalar Ollama en WSL
install_ollama_wsl() {
    print_info "Instalando Ollama en WSL..."

    # En WSL usamos el script oficial de Linux
    curl -fsSL https://ollama.com/install.sh | sh

    print_success "Ollama instalado correctamente"
    print_warning "Nota: Para usar Ollama en WSL,你需要 tener Ollama corriendo en Windows o en WSL"
    print_info "Puedes instalar Ollama para Windows desde https://ollama.com/download"
}

# Función para descargar el modelo
download_model() {
    local model=$1
    print_info "Descargando modelo: $model"

    # Verificar si el modelo ya existe
    if ollama list | grep -q "^${model}"; then
        print_success "El modelo $model ya está instalado"
        return 0
    fi

    print_info "Esto puede tomar varios minutos dependiendo de tu conexión a internet..."
    print_info "El modelo tiene aproximadamente 2GB"

    if ollama pull "$model"; then
        print_success "Modelo $model descargado correctamente"
        return 0
    else
        print_error "Error al descargar el modelo $model"
        return 1
    fi
}

# Función para iniciar el servicio Ollama
start_ollama_service() {
    print_info "Iniciando servicio Ollama..."

    # Verificar si ya está corriendo
    if check_ollama_running; then
        print_success "Ollama ya está corriendo"
        return 0
    fi

    # Iniciar Ollama en background
    if command -v systemctl &> /dev/null; then
        sudo systemctl start ollama
        sleep 2
        sudo systemctl enable ollama
    else
        # Ejecutar en background directamente
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi

    if check_ollama_running; then
        print_success "Servicio Ollama iniciado"
    else
        print_error "No se pudo iniciar el servicio Ollama"
        print_info "Revisa los logs con: tail -f /tmp/ollama.log"
        return 1
    fi
}

# Función para verificar la conexión con el LLM
test_connection() {
    print_info "Verificando conexión con Ollama..."

    # Test básico de conexión
    if ! curl -s http://localhost:11434/api/version &> /dev/null; then
        print_error "No se puede conectar a Ollama en http://localhost:11434"
        return 1
    fi

    print_success "Conexión exitosa con Ollama"

    # Test del modelo
    print_info "Probando generación de respuesta..."

    local test_response=$(curl -s http://localhost:11434/api/generate \
        -H "Content-Type: application/json" \
        -d '{
            "model": "llama3.2:3b",
            "prompt": "Responde solo con: HOLA",
            "stream": false
        }')

    if echo "$test_response" | grep -q "HOLA"; then
        print_success "Modelo funcionando correctamente"
    else
        print_warning "El modelo响应 pero no como se esperaba"
        print_info "response: $test_response"
    fi
}

# Función para mostrar instrucciones de uso
show_usage_instructions() {
    echo ""
    print_success "========================================="
    print_success "  Instalación completada exitosamente!"
    print_success "========================================="
    echo ""
    echo "Próximos pasos:"
    echo ""
    echo "1. Verifica que Ollama esté corriendo:"
    echo "   curl http://localhost:11434/api/version"
    echo ""
    echo "2. Para usar con audio2, asegúrate de que el servicio esté corriendo:"
    echo "   - En Linux con systemd: sudo systemctl start ollama"
    echo "   - En macOS: brew services start ollama"
    echo "   - Manual: ollama serve"
    echo ""
    echo "3. Los endpoints de IA estarán disponibles en:"
    echo "   - POST /ai/generate-playlist"
    echo "   - POST /ai/artist-bio"
    echo "   - POST /ai/album-summary"
    echo "   - POST /ai/recommendations"
    echo "   - POST /ai/semantic-search"
    echo "   - GET /ai/user-insights"
    echo ""
    echo "4. Documentación completa en: README_AI.md"
    echo ""
    echo "Troubleshooting:"
    echo "  - Si Ollama no responde: sudo systemctl status ollama"
    echo "  - Ver logs: journalctl -u ollama -f"
    echo "  - Reiniciar: sudo systemctl restart ollama"
    echo ""
}

# Función para manejar errores
handle_error() {
    print_error "Ocurrió un error en la línea $1"
    print_info "Revisa los mensajes anteriores para más detalles"
    exit 1
}

trap 'handle_error $LINEO' ERR

# Función principal
main() {
    echo "========================================="
    echo "  Audio2 - Instalador de Ollama"
    echo "========================================="
    echo ""

    # Detectar sistema operativo
    detect_os

    echo ""
    print_info "Iniciando instalación..."
    echo ""

    # Verificar si Ollama ya está instalado
    if check_ollama_installed; then
        print_success "Ollama ya está instalado"
    else
        print_info "Ollama no está instalado. Instalando..."

        case "$OS_FAMILY" in
            debian)
                install_ollama_debian
                ;;
            rhel)
                install_ollama_rhel
                ;;
            arch)
                install_ollama_arch
                ;;
            macos)
                install_ollama_macos
                ;;
            wsl)
                install_ollama_wsl
                ;;
            *)
                print_warning "Sistema no detectado, intentando instalación genérica..."
                curl -fsSL https://ollama.com/install.sh | sh
                ;;
        esac
    fi

    echo ""
    print_info "Verificando instalación..."
    ollama --version

    echo ""
    # Iniciar servicio
    start_ollama_service

    echo ""
    # Descargar modelo
    print_info "Configurando modelo Llama-3.2-3B..."
    download_model "llama3.2:3b"

    echo ""
    # Test de conexión
    test_connection

    echo ""
    # Mostrar instrucciones
    show_usage_instructions
}

# Ejecutar función principal
main "$@"
