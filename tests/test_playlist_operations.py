"""
Tests para operaciones de playlists (CRUD de tracks en playlists)
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select
from app.main import app
from app.core.db import get_session
from app.models.base import Playlist, PlaylistTrack, Track, Artist, Album


@pytest.fixture
def client():
    """Fixture para el cliente de test"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Fixture para sesión de base de datos"""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_playlist(db_session):
    """Crea una playlist de prueba"""
    playlist = Playlist(
        name="Test Playlist",
        description="Playlist para testing",
        user_id=1
    )
    db_session.add(playlist)
    db_session.commit()
    db_session.refresh(playlist)
    return playlist


@pytest.fixture
def sample_tracks(db_session):
    """Crea tracks de prueba"""
    # Crear artista primero
    artist = Artist(
        name="Test Artist",
        spotify_id="test_artist_123"
    )
    db_session.add(artist)
    db_session.commit()
    db_session.refresh(artist)
    
    # Crear álbum
    album = Album(
        name="Test Album",
        spotify_id="test_album_123",
        artist_id=artist.id
    )
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    
    # Crear tracks
    tracks = []
    for i in range(3):
        track = Track(
            name=f"Test Track {i+1}",
            spotify_id=f"test_track_{i+1}",
            artist_id=artist.id,
            album_id=album.id,
            duration_ms=180000
        )
        db_session.add(track)
        tracks.append(track)
    
    db_session.commit()
    for track in tracks:
        db_session.refresh(track)
    
    return tracks


class TestPlaylistTrackRemoval:
    """Tests para eliminación de tracks de playlists"""
    
    def test_remove_track_success(self, client, db_session, sample_playlist, sample_tracks):
        """Test: Eliminar un track existente de una playlist"""
        # Preparar: Añadir track a la playlist
        track = sample_tracks[0]
        playlist_track = PlaylistTrack(
            playlist_id=sample_playlist.id,
            track_id=track.id,
            order=1
        )
        db_session.add(playlist_track)
        db_session.commit()
        
        # Ejecutar
        response = client.delete(
            f"/playlists/id/{sample_playlist.id}/tracks/{track.id}"
        )
        
        # Verificar
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "eliminada" in data["message"].lower() or "removed" in data["message"].lower()
        
        # Verificar que realmente se eliminó de la BD
        remaining = db_session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == sample_playlist.id,
                PlaylistTrack.track_id == track.id
            )
        ).first()
        assert remaining is None
    
    def test_remove_track_not_found(self, client, db_session, sample_playlist):
        """Test: Intentar eliminar un track que no está en la playlist"""
        response = client.delete(
            f"/playlists/id/{sample_playlist.id}/tracks/99999"
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower() or "no encontrado" in data["detail"].lower()
    
    def test_remove_track_playlist_not_found(self, client):
        """Test: Intentar eliminar de una playlist que no existe"""
        response = client.delete("/playlists/id/99999/tracks/1")
        
        assert response.status_code == 404
    
    def test_remove_track_and_verify_other_tracks_remain(
        self, client, db_session, sample_playlist, sample_tracks
    ):
        """Test: Al eliminar un track, los demás deben permanecer"""
        # Preparar: Añadir múltiples tracks
        for i, track in enumerate(sample_tracks):
            playlist_track = PlaylistTrack(
                playlist_id=sample_playlist.id,
                track_id=track.id,
                order=i+1
            )
            db_session.add(playlist_track)
        db_session.commit()
        
        # Eliminar el primer track
        track_to_remove = sample_tracks[0]
        response = client.delete(
            f"/playlists/id/{sample_playlist.id}/tracks/{track_to_remove.id}"
        )
        
        assert response.status_code == 200
        
        # Verificar que los otros tracks siguen ahí
        remaining_tracks = db_session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == sample_playlist.id
            )
        ).all()
        
        assert len(remaining_tracks) == 2
        remaining_ids = {pt.track_id for pt in remaining_tracks}
        assert track_to_remove.id not in remaining_ids
        assert sample_tracks[1].id in remaining_ids
        assert sample_tracks[2].id in remaining_ids


class TestPlaylistTrackAddition:
    """Tests para inserción de tracks a playlists"""
    
    def test_add_track_success(self, client, db_session, sample_playlist, sample_tracks):
        """Test: Añadir un track a una playlist"""
        track = sample_tracks[0]
        
        response = client.post(
            f"/playlists/id/{sample_playlist.id}/tracks/{track.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["already_exists"] is False
        assert "playlist_track" in data
        
        # Verificar que realmente se guardó en la BD
        added = db_session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == sample_playlist.id,
                PlaylistTrack.track_id == track.id
            )
        ).first()
        assert added is not None
    
    def test_add_track_already_exists(self, client, db_session, sample_playlist, sample_tracks):
        """Test: Intentar añadir un track que ya está en la playlist"""
        track = sample_tracks[0]
        
        # Añadir primero
        playlist_track = PlaylistTrack(
            playlist_id=sample_playlist.id,
            track_id=track.id,
            order=1
        )
        db_session.add(playlist_track)
        db_session.commit()
        
        # Intentar añadir de nuevo
        response = client.post(
            f"/playlists/id/{sample_playlist.id}/tracks/{track.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["already_exists"] is True
        assert "already" in data["message"].lower() or "ya estaba" in data["message"].lower()
    
    def test_add_track_playlist_not_found(self, client, sample_tracks):
        """Test: Intentar añadir a una playlist que no existe"""
        track = sample_tracks[0]
        
        response = client.post(f"/playlists/id/99999/tracks/{track.id}")
        
        assert response.status_code == 404
    
    def test_add_track_track_not_found(self, client, sample_playlist):
        """Test: Intentar añadir un track que no existe"""
        response = client.post(f"/playlists/id/{sample_playlist.id}/tracks/99999")
        
        assert response.status_code == 404


class TestPlaylistIntegration:
    """Tests de integración: flujos completos"""
    
    def test_add_then_remove_track(
        self, client, db_session, sample_playlist, sample_tracks
    ):
        """Test: Añadir un track y luego eliminarlo"""
        track = sample_tracks[0]
        
        # Añadir
        add_response = client.post(
            f"/playlists/id/{sample_playlist.id}/tracks/{track.id}"
        )
        assert add_response.status_code == 200
        
        # Verificar que existe
        exists = db_session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == sample_playlist.id,
                PlaylistTrack.track_id == track.id
            )
        ).first()
        assert exists is not None
        
        # Eliminar
        remove_response = client.delete(
            f"/playlists/id/{sample_playlist.id}/tracks/{track.id}"
        )
        assert remove_response.status_code == 200
        
        # Verificar que ya no existe
        exists = db_session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == sample_playlist.id,
                PlaylistTrack.track_id == track.id
            )
        ).first()
        assert exists is None
    
    def test_playlist_tracks_endpoint_returns_correct_data(
        self, client, db_session, sample_playlist, sample_tracks
    ):
        """Test: El endpoint de tracks de playlist retorna datos correctos"""
        # Preparar: Añadir tracks
        for i, track in enumerate(sample_tracks[:2]):
            playlist_track = PlaylistTrack(
                playlist_id=sample_playlist.id,
                track_id=track.id,
                order=i+1
            )
            db_session.add(playlist_track)
        db_session.commit()
        
        # Obtener tracks
        response = client.get(f"/playlists/id/{sample_playlist.id}/tracks")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Verificar estructura de datos
        for track_data in data:
            assert "id" in track_data
            assert "name" in track_data
            assert "artist" in track_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
