import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { usePlayerStore } from '@/store/usePlayerStore';
import type { SpotifyTrack, TrackOverview, TrackPlaySummary, TrackRecentPlay } from '@/types/api';

export function Dashboard() {
  const nowPlaying = usePlayerStore((s) => s.nowPlaying);
  const recentPlays = usePlayerStore((s) => s.recentPlays);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const setVideoEmbedId = usePlayerStore((s) => s.setVideoEmbedId);
  const [favoriteTracks, setFavoriteTracks] = useState<TrackOverview[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [favoritesError, setFavoritesError] = useState<string | null>(null);
  const [recentlyAdded, setRecentlyAdded] = useState<TrackOverview[]>([]);
  const [recentlyAddedLoading, setRecentlyAddedLoading] = useState(false);
  const [recentlyAddedError, setRecentlyAddedError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<SpotifyTrack[]>([]);
  const [recommendationBase, setRecommendationBase] = useState<string[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null);
  const [mostPlayed, setMostPlayed] = useState<TrackPlaySummary[]>([]);
  const [mostPlayedLoading, setMostPlayedLoading] = useState(false);
  const [mostPlayedError, setMostPlayedError] = useState<string | null>(null);
  const [recentPlayHistory, setRecentPlayHistory] = useState<TrackRecentPlay[]>([]);
  const [recentPlayHistoryLoading, setRecentPlayHistoryLoading] = useState(false);
  const [recentPlayHistoryError, setRecentPlayHistoryError] = useState<string | null>(null);

  const playFromTrack = async (track: TrackOverview) => {
    const videoId =
      track.youtube_video_id ||
      (track.spotify_track_id
        ? (
            await audio2Api
              .refreshYoutubeTrackLink(track.spotify_track_id, {
                artist: track.artist_name || undefined,
                track: track.track_name || undefined,
                album: track.album_name || undefined,
              })
              .catch(() => null)
          )?.data?.youtube_video_id
        : null);
    if (!videoId) return;
    const durationSec = track.duration_ms ? Math.round(track.duration_ms / 1000) : undefined;
    await playByVideoId({
      spotifyTrackId: track.spotify_track_id || String(track.track_id),
      localTrackId: track.track_id,
      title: track.track_name || '—',
      artist: track.artist_name || undefined,
      artistSpotifyId: track.artist_spotify_id || undefined,
      videoId,
      durationSec,
    });
    if (playbackMode === 'video') {
      setVideoEmbedId(videoId);
    }
  };

  const playFromRecommendation = async (track: SpotifyTrack) => {
    const artistName = track.artists?.[0]?.name;
    if (!artistName) return;
    const response = await audio2Api
      .searchYoutubeMusic({
        artist: artistName,
        track: track.name,
        album: track.album?.name,
        max_results: 1,
      })
      .catch(() => null);
    const videoId = response?.data?.videos?.[0]?.video_id;
    if (!videoId) return;
    const durationSec = track.duration_ms ? Math.round(track.duration_ms / 1000) : undefined;
    await playByVideoId({
      spotifyTrackId: track.id,
      title: track.name,
      artist: artistName,
      artistSpotifyId: track.artists?.[0]?.id,
      videoId,
      durationSec,
    });
    if (playbackMode === 'video') {
      setVideoEmbedId(videoId);
    }
  };

  useEffect(() => {
    let active = true;
    const loadFavorites = async () => {
      setFavoritesLoading(true);
      setFavoritesError(null);
      try {
        const response = await audio2Api.getTracksOverview({
          filter: 'favorites',
          limit: 6,
          include_summary: false,
          verify_files: false,
        });
        if (!active) return;
        setFavoriteTracks(Array.isArray(response.data.items) ? response.data.items : []);
      } catch (error) {
        if (!active) return;
        console.error('Favorites load failed:', error);
        setFavoritesError('No se pudieron cargar los favoritos.');
      } finally {
        if (active) setFavoritesLoading(false);
      }
    };

    loadFavorites();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const loadRecentlyAdded = async () => {
      setRecentlyAddedLoading(true);
      setRecentlyAddedError(null);
      try {
        const response = await audio2Api.getRecentlyAddedTracks({ limit: 6 });
        if (!active) return;
        setRecentlyAdded(Array.isArray(response.data.items) ? response.data.items : []);
      } catch (error) {
        if (!active) return;
        console.error('Recently added load failed:', error);
        setRecentlyAddedError('No se pudieron cargar las nuevas incorporaciones.');
      } finally {
        if (active) setRecentlyAddedLoading(false);
      }
    };

    loadRecentlyAdded();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const loadMostPlayed = async () => {
      setMostPlayedLoading(true);
      setMostPlayedError(null);
      try {
        const response = await audio2Api.getMostPlayedTracks({ limit: 6 });
        if (!active) return;
        setMostPlayed(Array.isArray(response.data.items) ? response.data.items : []);
      } catch (error) {
        if (!active) return;
        console.error('Most played load failed:', error);
        setMostPlayedError('No se pudieron cargar las mas escuchadas.');
      } finally {
        if (active) setMostPlayedLoading(false);
      }
    };

    loadMostPlayed();
    return () => {
      active = false;
    };
  }, [recentPlays.length]);

  useEffect(() => {
    let active = true;
    const loadRecentPlays = async () => {
      setRecentPlayHistoryLoading(true);
      setRecentPlayHistoryError(null);
      try {
        const response = await audio2Api.getRecentPlays({ limit: 6 });
        if (!active) return;
        setRecentPlayHistory(Array.isArray(response.data.items) ? response.data.items : []);
      } catch (error) {
        if (!active) return;
        console.error('Recent plays load failed:', error);
        setRecentPlayHistoryError('No se pudieron cargar las ultimas escuchas.');
      } finally {
        if (active) setRecentPlayHistoryLoading(false);
      }
    };

    loadRecentPlays();
    return () => {
      active = false;
    };
  }, [recentPlays.length]);

  useEffect(() => {
    const seedArtists = Array.from(
      new Set(
        recentPlays
          .map((play) => play.artistSpotifyId)
          .filter((artistId): artistId is string => Boolean(artistId))
          .filter((artistId) => /^[A-Za-z0-9]{22}$/.test(artistId))
      )
    ).slice(0, 3);
    const seedArtistNames = recentPlays
      .filter((play) => play.artistSpotifyId && seedArtists.includes(play.artistSpotifyId))
      .map((play) => play.artist || play.title)
      .filter(Boolean)
      .slice(0, 3);
    const seedTracks = Array.from(
      new Set(
        recentPlays
          .map((play) => play.spotifyTrackId)
          .filter((trackId) => /^[A-Za-z0-9]{22}$/.test(trackId))
      )
    ).slice(0, 3);
    const localSeedTracks = Array.from(
      new Set(
        recentPlays
          .map((play) => {
            if (typeof play.localTrackId === 'number') {
              return String(play.localTrackId);
            }
            return /^\d+$/.test(play.spotifyTrackId) ? play.spotifyTrackId : null;
          })
          .filter((trackId): trackId is string => Boolean(trackId))
      )
    ).slice(0, 3);
    const combinedSeedTracks = Array.from(new Set([...seedTracks, ...localSeedTracks]));
    const nameSeedTracks = seedTracks.length ? seedTracks : localSeedTracks;
    const seedNames = seedArtistNames.length > 0
      ? seedArtistNames
      : recentPlays
          .filter((play) => {
            const localId = typeof play.localTrackId === 'number'
              ? String(play.localTrackId)
              : (/^\d+$/.test(play.spotifyTrackId) ? play.spotifyTrackId : null);
            const matchId = seedTracks.length ? play.spotifyTrackId : localId;
            return Boolean(matchId && nameSeedTracks.includes(matchId));
          })
          .map((play) => play.title)
          .slice(0, 3);
    if (!combinedSeedTracks.length && !seedArtists.length) {
      setRecommendations([]);
      setRecommendationBase([]);
      return;
    }
    let active = true;
    const loadRecommendations = async () => {
      setRecommendationsLoading(true);
      setRecommendationsError(null);
      try {
        const response = await audio2Api.getTrackRecommendations({
          seed_tracks: seedArtists.length ? undefined : combinedSeedTracks,
          seed_artists: seedArtists.length ? seedArtists : undefined,
          limit: 12,
        });
        if (!active) return;
        const payload = response.data;
        setRecommendations(Array.isArray(payload.tracks) ? payload.tracks : []);
        setRecommendationBase(seedNames);
      } catch (error) {
        if (!active) return;
        console.error('Recommendations load failed:', error);
        const message =
          error && typeof error === 'object' && 'response' in error && error.response && typeof error.response === 'object' && 'data' in error.response && error.response.data && typeof error.response.data === 'object' && 'detail' in error.response.data
            ? (error.response.data as { detail: string }).detail
            : 'No se pudieron cargar recomendaciones.';
        setRecommendationsError(message);
      } finally {
        if (active) setRecommendationsLoading(false);
      }
    };

    loadRecommendations();
    return () => {
      active = false;
    };
  }, [recentPlays]);

  const recommendationSubtitle = recommendationBase.length > 0
    ? `Basado en: ${recommendationBase.slice(0, 3).join(', ')}`
    : 'Basado en tus ultimas escuchas';

  return (
    <div className="space-y-5">
      <div className="card dashboard-hero">
        <div className="dashboard-hero__title">Tu musica, siempre lista</div>
        <p className="dashboard-hero__subtitle">
          Favoritos, playlists y recomendaciones inteligentes para mantener el ritmo.
        </p>
        <div className="dashboard-hero__actions">
          <Link className="btn-accent" to="/search">Buscar artistas</Link>
          <Link className="btn-ghost" to="/tracks">Ir a tracks</Link>
          <Link className="btn-ghost" to="/downloads">Descargas</Link>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="card dashboard-section">
          <div className="dashboard-section__header">
            <div>
              <div className="dashboard-section__title">Favoritos</div>
              <div className="dashboard-section__subtitle">Tus pistas clave primero</div>
            </div>
            <Link className="btn-ghost" to="/tracks">Ver todos</Link>
          </div>
          {favoritesLoading ? (
            <div className="dashboard-empty">Cargando favoritos...</div>
          ) : favoritesError ? (
            <div className="dashboard-empty">{favoritesError}</div>
          ) : favoriteTracks.length === 0 ? (
            <div className="dashboard-empty">
              Todavia no tienes favoritos. Marca algunas pistas en tracks.
            </div>
          ) : (
            <div className="dashboard-list">
              {favoriteTracks.map((track) => (
                <button
                  key={track.track_id}
                  className="dashboard-list__item"
                  onClick={() => void playFromTrack(track)}
                  type="button"
                  style={{ textAlign: 'left', cursor: 'pointer' }}
                >
                  <div className="dashboard-list__text">
                    <div className="dashboard-list__title">{track.track_name || 'Sin titulo'}</div>
                    <div className="dashboard-list__meta">{track.artist_name || 'Artista desconocido'}</div>
                  </div>
                  <div className="dashboard-list__meta">
                    {track.local_file_exists ? 'MP3' : 'Stream'}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="card dashboard-section">
          <div className="dashboard-section__header">
            <div>
              <div className="dashboard-section__title">Playlists</div>
              <div className="dashboard-section__subtitle">Colecciones listas para sonar</div>
            </div>
            <Link className="btn-ghost" to="/playlists">Ver todas</Link>
          </div>
          <div className="dashboard-tags">
            {['Favoritos', 'Top Rated', 'Recientes', 'Descargas', 'Para entrenar', 'Noches'].map((tag) => (
              <span key={tag} className="dashboard-tag">{tag}</span>
            ))}
          </div>
          <div className="dashboard-empty">
            Las playlists inteligentes se llenan a medida que marcas favoritos.
          </div>
        </section>
      </div>

      <section className="card dashboard-section">
        <div className="dashboard-section__header">
          <div>
            <div className="dashboard-section__title">Recomendaciones</div>
            <div className="dashboard-section__subtitle">{recommendationSubtitle}</div>
          </div>
          <Link className="btn-ghost" to="/artists">Explorar</Link>
        </div>
        {recommendationsLoading ? (
          <div className="dashboard-empty">Buscando nuevas recomendaciones...</div>
        ) : recommendationsError ? (
          <div className="dashboard-empty">{recommendationsError}</div>
        ) : recommendations.length === 0 ? (
          <div className="dashboard-empty">
            Escucha y busca artistas para generar recomendaciones personalizadas.
          </div>
        ) : (
          <div className="grid-cards">
            {recommendations.map((rec) => (
              <button
                key={rec.id}
                className="card dashboard-rec"
                onClick={() => void playFromRecommendation(rec)}
                type="button"
                style={{ textAlign: 'left', cursor: 'pointer' }}
              >
                <div className="dashboard-rec__title">{rec.name}</div>
                <div className="dashboard-rec__meta">
                  {(rec.artists || []).map((artist) => artist.name).slice(0, 3).join(', ') || 'Artista recomendado'}
                </div>
                <div className="dashboard-rec__score">Spotify recomienda</div>
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="dashboard-grid">
        <section className="card dashboard-section">
          <div className="dashboard-section__header">
            <div>
              <div className="dashboard-section__title">Nuevas incorporaciones</div>
              <div className="dashboard-section__subtitle">Lo ultimo en tus tracks</div>
            </div>
            <Link className="btn-ghost" to="/tracks">Ver tracks</Link>
          </div>
          {recentlyAddedLoading ? (
            <div className="dashboard-empty">Cargando nuevas incorporaciones...</div>
          ) : recentlyAddedError ? (
            <div className="dashboard-empty">{recentlyAddedError}</div>
          ) : recentlyAdded.length === 0 ? (
            <div className="dashboard-empty">No hay pistas nuevas registradas.</div>
          ) : (
            <div className="dashboard-list">
              {recentlyAdded.map((track) => (
                <button
                  key={track.track_id}
                  className="dashboard-list__item"
                  onClick={() => void playFromTrack(track)}
                  type="button"
                  style={{ textAlign: 'left', cursor: 'pointer' }}
                >
                  <div className="dashboard-list__text">
                    <div className="dashboard-list__title">{track.track_name || 'Sin titulo'}</div>
                    <div className="dashboard-list__meta">{track.artist_name || 'Artista desconocido'}</div>
                  </div>
                  <div className="dashboard-list__meta">{track.album_name || 'Album'}</div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="card dashboard-section">
          <div className="dashboard-section__header">
            <div>
              <div className="dashboard-section__title">Mas escuchadas</div>
              <div className="dashboard-section__subtitle">Basado en tu historial</div>
            </div>
            <Link className="btn-ghost" to="/tracks">Abrir tracks</Link>
          </div>
          {mostPlayedLoading ? (
            <div className="dashboard-empty">Cargando historial...</div>
          ) : mostPlayedError ? (
            <div className="dashboard-empty">{mostPlayedError}</div>
          ) : mostPlayed.length === 0 ? (
            <div className="dashboard-empty">Aun no hay suficientes reproducciones.</div>
          ) : (
            <div className="dashboard-list">
              {mostPlayed.map((track) => (
                <button
                  key={track.track_id}
                  className="dashboard-list__item"
                  onClick={() => void playFromTrack(track)}
                  type="button"
                  style={{ textAlign: 'left', cursor: 'pointer' }}
                >
                  <div className="dashboard-list__text">
                    <div className="dashboard-list__title">{track.track_name || 'Sin titulo'}</div>
                    <div className="dashboard-list__meta">{track.artist_name || 'Artista desconocido'}</div>
                  </div>
                  <div className="dashboard-list__meta">{track.play_count} reproducciones</div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="card dashboard-section">
          <div className="dashboard-section__header">
            <div>
              <div className="dashboard-section__title">Ultimas escuchas</div>
              <div className="dashboard-section__subtitle">Historial rapido de reproduccion</div>
            </div>
            <Link className="btn-ghost" to="/tracks">Abrir tracks</Link>
          </div>
        {recentPlayHistoryLoading ? (
          <div className="dashboard-empty">Cargando reproducciones...</div>
        ) : recentPlayHistoryError ? (
          <div className="dashboard-empty">{recentPlayHistoryError}</div>
        ) : recentPlayHistory.length > 0 ? (
          <div className="dashboard-list">
            {recentPlayHistory.map((play, index) => (
              <button
                key={`${play.track_id}-${play.played_at || index}`}
                className="dashboard-list__item"
                onClick={() => void playFromTrack(play)}
                type="button"
                style={{ textAlign: 'left', cursor: 'pointer' }}
              >
                <div className="dashboard-list__text">
                  <div className="dashboard-list__title">{play.track_name || 'Sin titulo'}</div>
                  <div className="dashboard-list__meta">{play.artist_name || 'Artista desconocido'}</div>
                </div>
                <div className="dashboard-list__meta">
                  {nowPlaying?.localTrackId === play.track_id && index === 0 ? 'Ahora' : 'Reciente'}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="dashboard-empty">Aun no hay reproducciones guardadas.</div>
        )}
      </section>
    </div>
  );
}
