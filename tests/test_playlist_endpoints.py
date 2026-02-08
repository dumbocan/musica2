"""
Tests simplificados para verificar la lógica de playlists
Estos tests verifican que los endpoints responden correctamente
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Fixture para el cliente de test"""
    return TestClient(app)


class TestPlaylistEndpoints:
    """Tests básicos para endpoints de playlists"""
    
    def test_get_playlists_endpoint_exists(self, client):
        """Verifica que el endpoint GET /playlists/ existe"""
        response = client.get("/playlists/")
        # Puede devolver 200 (si hay playlists) o cualquier otro código, pero no 404
        assert response.status_code != 404
    
    def test_add_track_to_playlist_endpoint_not_found_cases(self, client):
        """Verifica manejo de casos no encontrados"""
        # Intentar añadir a playlist que no existe
        response = client.post("/playlists/id/99999/tracks/1")
        assert response.status_code == 404
        
        # Intentar añadir track que no existe a playlist que no existe
        response = client.post("/playlists/id/99999/tracks/99999")
        assert response.status_code == 404
    
    def test_remove_track_from_playlist_endpoint_not_found_cases(self, client):
        """Verifica manejo de casos no encontrados al eliminar"""
        # Intentar eliminar de playlist que no existe
        response = client.delete("/playlists/id/99999/tracks/1")
        assert response.status_code == 404
    
    def test_get_playlist_tracks_endpoint_exists(self, client):
        """Verifica que el endpoint GET /playlists/id/{id}/tracks existe"""
        # Usar ID que seguramente no existe
        response = client.get("/playlists/id/99999/tracks")
        # Puede devolver 404 (playlist no existe) pero no debe dar error 500
        assert response.status_code in [200, 404]


class TestPlaylistResponseFormats:
    """Tests para verificar formatos de respuesta"""
    
    def test_remove_track_response_format(self, client):
        """Verifica que la respuesta de eliminación tiene el formato correcto"""
        # Intentar eliminar track inexistente
        response = client.delete("/playlists/id/99999/tracks/1")
        
        if response.status_code == 404:
            data = response.json()
            # Debe tener campo detail
            assert "detail" in data
    
    def test_add_track_response_format(self, client):
        """Verifica que la respuesta de adición tiene el formato correcto"""
        # Intentar añadir a playlist inexistente
        response = client.post("/playlists/id/99999/tracks/1")
        
        if response.status_code == 404:
            data = response.json()
            # Debe tener campo detail
            assert "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
