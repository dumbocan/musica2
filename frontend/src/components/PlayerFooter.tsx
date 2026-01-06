import { useEffect, useMemo, useRef } from 'react';
import { usePlayerStore } from '@/store/usePlayerStore';

export function PlayerFooter() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const nowPlaying = usePlayerStore((s) => s.nowPlaying);
  const queue = usePlayerStore((s) => s.queue);
  const currentIndex = usePlayerStore((s) => s.currentIndex);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const currentTime = usePlayerStore((s) => s.currentTime);
  const duration = usePlayerStore((s) => s.duration);
  const volume = usePlayerStore((s) => s.volume);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const audioSourceMode = usePlayerStore((s) => s.audioSourceMode);
  const statusMessage = usePlayerStore((s) => s.statusMessage);
  const onPlayTrack = usePlayerStore((s) => s.onPlayTrack);
  const videoControls = usePlayerStore((s) => s.videoControls);
  const setAudioEl = usePlayerStore((s) => s.setAudioEl);
  const setCurrentTime = usePlayerStore((s) => s.setCurrentTime);
  const setDuration = usePlayerStore((s) => s.setDuration);
  const setIsPlaying = usePlayerStore((s) => s.setIsPlaying);
  const setVolume = usePlayerStore((s) => s.setVolume);
  const setPlaybackMode = usePlayerStore((s) => s.setPlaybackMode);
  const setStatusMessage = usePlayerStore((s) => s.setStatusMessage);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const tryUpgradeToFile = usePlayerStore((s) => s.tryUpgradeToFile);
  const resumeAudio = usePlayerStore((s) => s.resumeAudio);
  const pauseAudio = usePlayerStore((s) => s.pauseAudio);
  const stopAudio = usePlayerStore((s) => s.stopAudio);
  const seekAudio = usePlayerStore((s) => s.seekAudio);
  const upgradeInFlightRef = useRef(false);

  const prevItem = currentIndex > 0 ? queue[currentIndex - 1] : null;
  const nextItem = currentIndex >= 0 && currentIndex < queue.length - 1 ? queue[currentIndex + 1] : null;

  useEffect(() => {
    if (!audioRef.current) return;
    setAudioEl(audioRef.current);
    return () => setAudioEl(null);
  }, [setAudioEl]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handleTime = () => setCurrentTime(audio.currentTime || 0);
    const handleLoaded = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        setDuration(audio.duration);
      }
    };
    const handlePlay = () => {
      setIsPlaying(true);
      setStatusMessage('');
    };
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };
    const handleError = () => setStatusMessage('No se pudo reproducir el audio');
    audio.addEventListener('timeupdate', handleTime);
    audio.addEventListener('loadedmetadata', handleLoaded);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('playing', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);
    return () => {
      audio.removeEventListener('timeupdate', handleTime);
      audio.removeEventListener('loadedmetadata', handleLoaded);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('playing', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, [setCurrentTime, setDuration, setIsPlaying, setStatusMessage]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = Math.max(0, Math.min(volume, 100)) / 100;
  }, [volume]);

  useEffect(() => {
    if (playbackMode !== 'audio') return;
    const audio = audioRef.current;
    if (!audio) return;
    let raf = 0;
    const tick = () => {
      if (!audio.paused) {
        const nextTime = audio.currentTime || 0;
        if (Number.isFinite(nextTime)) {
          setCurrentTime(nextTime);
        }
        if (!Number.isFinite(duration) || duration <= 0) {
          const mediaDuration = audio.duration;
          if (Number.isFinite(mediaDuration) && mediaDuration > 0) {
            setDuration(mediaDuration);
          }
        }
      }
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [duration, playbackMode, setCurrentTime, setDuration]);

  useEffect(() => {
    if (playbackMode !== 'audio') return;
    if (!nowPlaying || audioSourceMode !== 'stream') return;
    let interval = 0;
    interval = window.setInterval(async () => {
      if (upgradeInFlightRef.current) return;
      upgradeInFlightRef.current = true;
      try {
        await tryUpgradeToFile();
      } finally {
        upgradeInFlightRef.current = false;
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [audioSourceMode, nowPlaying?.videoId, playbackMode, tryUpgradeToFile]);

  const formatTime = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return '0:00';
    const mins = Math.floor(value / 60);
    const secs = Math.floor(value % 60);
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const progressPercent = duration > 0 ? Math.min((currentTime / duration) * 100, 100) : 0;
  const canSeek = playbackMode === 'video' || audioSourceMode !== 'stream';
  const hasValidYoutubeId = nowPlaying?.videoId ? /^[A-Za-z0-9_-]{11}$/.test(nowPlaying.videoId) : false;
  const footerStatus = useMemo(() => {
    if (!nowPlaying) return 'Pausado';
    if (statusMessage) return statusMessage;
    return isPlaying ? 'Reproduciendo' : 'Pausado';
  }, [isPlaying, nowPlaying, statusMessage]);

  const handlePlay = () => {
    if (!nowPlaying) return;
    if (playbackMode === 'video') {
      videoControls?.play?.();
      return;
    }
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.src || !audio.src.includes(nowPlaying.videoId)) {
      void playByVideoId(nowPlaying);
      return;
    }
    resumeAudio();
  };

  const handlePause = () => {
    if (playbackMode === 'video') {
      videoControls?.pause?.();
      return;
    }
    pauseAudio();
  };

  const handleStop = () => {
    if (playbackMode === 'video') {
      videoControls?.stop?.();
      return;
    }
    stopAudio();
  };

  const handleSeek = (value: number) => {
    if (playbackMode === 'video') {
      videoControls?.seek?.(value);
      return;
    }
    seekAudio(value);
  };

  const handlePrev = () => {
    if (!prevItem || !onPlayTrack) return;
    onPlayTrack(prevItem);
  };

  const handleNext = () => {
    if (!nextItem || !onPlayTrack) return;
    onPlayTrack(nextItem);
  };

  return (
    <footer className="album-player">
      <div className="album-player__left">
        <button className="album-player__btn" onClick={handlePrev} disabled={!prevItem || !onPlayTrack} title="Anterior">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M19 5L11 12L19 19V5z" />
            <path d="M13 5L5 12L13 19V5z" />
          </svg>
        </button>
        <button className="album-player__btn album-player__btn--primary" onClick={handlePlay} disabled={!nowPlaying} title="Reproducir">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5L19 12L8 19V5z" />
          </svg>
        </button>
        <button className="album-player__btn" onClick={handlePause} disabled={!nowPlaying} title="Pausar">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 5h4v14H6z" />
            <path d="M14 5h4v14h-4z" />
          </svg>
        </button>
        <button className="album-player__btn" onClick={handleNext} disabled={!nextItem || !onPlayTrack} title="Siguiente">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5L13 12L5 19V5z" />
            <path d="M11 5L19 12L11 19V5z" />
          </svg>
        </button>
        <button className="album-player__btn" onClick={handleStop} disabled={!nowPlaying} title="Detener">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6h12v12H6z" />
          </svg>
        </button>
      </div>
      <div className="album-player__timeline">
        <div className="album-player__track">
          {nowPlaying ? `Reproduciendo: ${nowPlaying.title} · ${nowPlaying.artist || ''}` : 'Selecciona una canción para reproducir'}
        </div>
        <div className="album-player__progress">
          <span className="album-player__time">{formatTime(currentTime)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={1}
            value={duration > 0 ? Math.min(currentTime, duration) : 0}
            onChange={(e) => handleSeek(Number(e.target.value))}
            disabled={!nowPlaying || !duration || !canSeek}
            className="album-player__slider"
            style={{ ['--progress' as any]: `${progressPercent}%` }}
            aria-label="Progreso"
          />
          <span className="album-player__time">{formatTime(duration)}</span>
        </div>
      </div>

      <div className="album-player__right">
        <div className="album-player__mode">
          <button
            className={`album-player__mode-btn ${playbackMode === 'audio' ? 'is-active' : ''}`}
            onClick={() => setPlaybackMode('audio')}
            type="button"
          >
            Audio
          </button>
          <button
            className={`album-player__mode-btn ${playbackMode === 'video' ? 'is-active' : ''}`}
            onClick={() => setPlaybackMode('video')}
            type="button"
            disabled={!videoControls}
            title={!videoControls ? 'Video solo disponible en la página del álbum' : 'Video'}
          >
            Video
          </button>
        </div>
        <div className="album-player__volume">
          <span>VOL</span>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="album-player__slider album-player__slider--volume"
            style={{ ['--progress' as any]: `${volume}%` }}
            aria-label="Volumen"
          />
        </div>
        {nowPlaying && hasValidYoutubeId && (
          <a
            className="album-player__link"
            href={`https://www.youtube.com/watch?v=${nowPlaying.videoId}`}
            target="_blank"
            rel="noreferrer"
          >
            Abrir en YouTube
          </a>
        )}
        <span className="album-player__status" style={{ color: isPlaying || statusMessage ? '#4ade80' : 'var(--muted)' }}>
          {footerStatus}
        </span>
      </div>
      <audio ref={audioRef} preload="metadata" style={{ display: 'none' }} aria-hidden="true" />
    </footer>
  );
}
