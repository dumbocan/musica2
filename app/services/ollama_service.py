"""
Ollama Service - Conexión y comunicación con LLM local.

Este módulo proporciona una interfaz limpia para interactuar con Ollama
que corre localmente. Maneja la conexión, generación de respuestas,
y errores de manera robusta.

Usage:
    from services.ollama_service import ollama_client

    response = ollama_client.generate(
        prompt="Genera una playlist de música rock",
        system_prompt="Eres un experto en música..."
    )
"""

import json
import requests
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
import time

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Configuración del cliente Ollama."""
    base_url: str = "http://localhost:11434"
    model: str = "tinyllama:1.1b"
    timeout: int = 300  # segundos para generación
    max_retries: int = 3
    retry_delay: float = 1.0  # segundos entre reintentos


@dataclass
class OllamaResponse:
    """Respuesta estructurada del LLM."""
    text: str
    raw_response: Dict[str, Any]
    model: str
    tokens: int
    duration_ms: int
    success: bool
    error: Optional[str] = None


class OllamaConnectionError(Exception):
    """Error de conexión con Ollama."""
    pass


class OllamaModelError(Exception):
    """Error del modelo durante generación."""
    pass


class OllamaClient:
    """
    Cliente para interactuar con Ollama local.

    Maneja:
    - Conexión y verificación de estado
    - Generación de texto
    - Manejo de errores
    - Reintentos automáticos
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        """
        Inicializar el cliente Ollama.

        Args:
            config: Configuración personalizada (opcional)
        """
        self.config = config or OllamaConfig()
        self._session = requests.Session()
        self._last_health_check: Optional[datetime] = None

    def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        timeout: Optional[int] = None,
        method: str = "POST"
    ) -> Dict[str, Any]:
        """
        Hacer request a la API de Ollama.

        Args:
            endpoint: Endpoint de la API (sin base_url)
            data: Datos a enviar en JSON
            timeout: Timeout override (opcional)
            method: Método HTTP ("POST" o "GET")

        Returns:
            Dict con la respuesta

        Raises:
            OllamaConnectionError: Si no se puede conectar
            OllamaModelError: Si el modelo responde con error
        """
        url = f"{self.config.base_url}{endpoint}"
        timeout = timeout or self.config.timeout

        for attempt in range(self.config.max_retries):
            try:
                if method.upper() == "GET":
                    response = self._session.get(url, timeout=timeout)
                else:
                    response = self._session.post(
                        url,
                        json=data,
                        timeout=timeout
                    )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.ConnectionError as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(
                        f"Intento {attempt + 1} falló, reintentando en "
                        f"{self.config.retry_delay}s..."
                    )
                    time.sleep(self.config.retry_delay)
                    continue
                raise OllamaConnectionError(
                    f"No se puede conectar a Ollama en {url}. "
                    f"¿Está Ollama corriendo?"
                ) from e

            except requests.exceptions.Timeout as e:
                raise OllamaConnectionError(
                    f"Timeout esperando respuesta de Ollama ({timeout}s)"
                ) from e

            except requests.exceptions.HTTPError as e:
                error_text = e.response.text if e.response else "Sin detalles"
                raise OllamaModelError(
                    f"Error HTTP {e.response.status_code}: {error_text}"
                ) from e

        raise OllamaConnectionError("Máximo número de reintentos alcanzado")

    def is_available(self) -> bool:
        """
        Verificar si Ollama está disponible.

        Returns:
            True si está disponible, False si no
        """
        try:
            self._make_request("/api/version", {}, method="GET")
            self._last_health_check = datetime.now()
            return True
        except (OllamaConnectionError, OllamaModelError):
            return False

    def get_version(self) -> Optional[str]:
        """
        Obtener la versión de Ollama.

        Returns:
            String de versión o None si no está disponible
        """
        try:
            response = self._make_request("/api/version", {}, method="GET")
            return response.get("version")
        except (OllamaConnectionError, OllamaModelError):
            return None

    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Obtener información del modelo cargado.

        Returns:
            Dict con info del modelo o None
        """
        try:
            # Para obtener info del modelo, usamos /api/tags
            response = self._make_request("/api/tags", {}, method="GET")
            models = response.get("models", [])

            # Buscar nuestro modelo
            model_name = self.config.model
            for model in models:
                if model.get("name", "").startswith(model_name):
                    return {
                        "name": model["name"],
                        "size": model.get("size", 0),
                        "digest": model.get("digest", ""),
                    }

            return None
        except (OllamaConnectionError, OllamaModelError):
            return None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        format: Optional[str] = None,  # "json" para respuestas JSON
    ) -> OllamaResponse:
        """
        Generar texto usando el LLM.

        Args:
            prompt: Prompt del usuario
            system_prompt: Prompt del sistema (opcional)
            temperature: Temperatura de generación (0.0-1.0)
            max_tokens: Máximo de tokens a generar (None = automático)
            stream: Si True, retorna generator (no implementado aún)
            format: Formato de respuesta ("json" para JSON)

        Returns:
            OllamaResponse con la respuesta estructurada
        """
        start_time = time.time()

        # Construir el payload
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
            }
        }

        # Agregar system prompt si existe
        if system_prompt:
            payload["system"] = system_prompt

        # Agregar max_tokens si se especifica
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Forzar respuesta JSON si se solicita
        if format == "json":
            payload["format"] = "json"

        try:
            response = self._make_request("/api/generate", payload)

            # Extraer datos de la respuesta
            text = response.get("response", "")
            tokens = response.get("eval_count", 0)
            duration_ms = int((time.time() - start_time) * 1000)

            return OllamaResponse(
                text=text,
                raw_response=response,
                model=self.config.model,
                tokens=tokens,
                duration_ms=duration_ms,
                success=True
            )

        except (OllamaConnectionError, OllamaModelError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return OllamaResponse(
                text="",
                raw_response={},
                model=self.config.model,
                tokens=0,
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            )

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_schema: Dict[str, Any],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> OllamaResponse:
        """
        Generar respuesta y parsear como JSON estructurado.

        Args:
            prompt: Prompt del usuario
            system_prompt: Prompt del sistema
            response_schema: Schema JSON esperado en la respuesta
            temperature: Temperatura de generación

        Returns:
            OllamaResponse con la respuesta parseada
        """
        # Modificar el system prompt para solicitar JSON
        schema_json = json.dumps(response_schema, ensure_ascii=False, separators=(",", ":"))
        enhanced_system = f"""{system_prompt}

IMPORTANTE: Debes responder exclusivamente con JSON válido.
No incluyas texto adicional, markdown, ni explicaciones.
Tu respuesta debe ser un objeto JSON que siga este esquema:
{schema_json}
"""

        # Modelos muy pequeños suelen quedarse largos en modo JSON; limitamos salida.
        if max_tokens is None and ("0.5b" in self.config.model or "1.5b" in self.config.model):
            max_tokens = 256

        response = self.generate(
            prompt=prompt,
            system_prompt=enhanced_system,
            temperature=temperature,
            format="json",
            max_tokens=max_tokens,
        )

        return response

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
    ) -> OllamaResponse:
        """
        Generación usando formato de chat (messages array).

        Args:
            messages: Lista de mensajes con role y content
            temperature: Temperatura de generación

        Returns:
            OllamaResponse con la respuesta
        """
        start_time = time.time()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        try:
            response = self._make_request("/api/chat", payload)

            text = response.get("message", {}).get("response", "")
            tokens = response.get("eval_count", 0)
            duration_ms = int((time.time() - start_time) * 1000)

            return OllamaResponse(
                text=text,
                raw_response=response,
                model=self.config.model,
                tokens=tokens,
                duration_ms=duration_ms,
                success=True
            )

        except (OllamaConnectionError, OllamaModelError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return OllamaResponse(
                text="",
                raw_response={},
                model=self.config.model,
                tokens=0,
                duration_ms=duration_ms,
                success=False,
                error=str(e)
            )

    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generar embedding de un texto (si el modelo lo soporta).

        Args:
            text: Texto a embeddar

        Returns:
            Lista de floats o None si no está disponible
        """
        # Ollama 0.1.x usa /api/embeddings
        try:
            payload = {
                "model": self.config.model,
                "prompt": text,
            }
            response = self._make_request("/api/embeddings", payload)
            return response.get("embedding")

        except (OllamaConnectionError, OllamaModelError):
            return None


# Instancia global del cliente
ollama_client = OllamaClient()


def require_ollama(func):
    """
    Decorador para requerir que Ollama esté disponible.

    Usage:
        @require_ollama
        def mi_funcion():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not ollama_client.is_available():
            raise OllamaConnectionError(
                "Ollama no está disponible. "
                "Asegúrate de que el servicio esté corriendo en localhost:11434"
            )
        return func(*args, **kwargs)
    return wrapper


def check_ollama_health() -> Dict[str, Any]:
    """
    Verificar el estado completo de Ollama.

    Returns:
        Dict con estado de salud
    """
    status = {
        "available": False,
        "version": None,
        "model": None,
        "model_info": None,
        "error": None,
    }

    try:
        status["available"] = ollama_client.is_available()
        status["version"] = ollama_client.get_version()
        status["model_info"] = ollama_client.get_model_info()
        status["model"] = ollama_client.config.model

        if status["available"]:
            status["error"] = None
        else:
            status["error"] = "Ollama no está respondiendo"

    except Exception as e:
        status["error"] = str(e)

    return status
