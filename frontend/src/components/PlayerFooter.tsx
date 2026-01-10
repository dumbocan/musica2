import { useCallback, useEffect, useMemo, useRef } from 'react';
import { usePlayerStore } from '@/store/usePlayerStore';
import { audio2Api } from '@/lib/api';

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
  const videoEmbedId = usePlayerStore((s) => s.videoEmbedId);
  const videoController = usePlayerStore((s) => s.videoController);
  const audioSourceMode = usePlayerStore((s) => s.audioSourceMode);
  const statusMessage = usePlayerStore((s) => s.statusMessage);
  const audioDownloadStatus = usePlayerStore((s) => s.audioDownloadStatus);
  const audioDownloadVideoId = usePlayerStore((s) => s.audioDownloadVideoId);
  const onPlayTrack = usePlayerStore((s) => s.onPlayTrack);
  const setVideoDownloadState = usePlayerStore((s) => s.setVideoDownloadState);
  const setLastDownloadedVideo = usePlayerStore((s) => s.setLastDownloadedVideo);
  const setAudioEl = usePlayerStore((s) => s.setAudioEl);
  const setCurrentTime = usePlayerStore((s) => s.setCurrentTime);
  const setDuration = usePlayerStore((s) => s.setDuration);
  const setIsPlaying = usePlayerStore((s) => s.setIsPlaying);
  const setVolume = usePlayerStore((s) => s.setVolume);
  const setPlaybackMode = usePlayerStore((s) => s.setPlaybackMode);
  const setStatusMessage = usePlayerStore((s) => s.setStatusMessage);
  const setVideoEmbedId = usePlayerStore((s) => s.setVideoEmbedId);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const tryUpgradeToFile = usePlayerStore((s) => s.tryUpgradeToFile);
  const resumeAudio = usePlayerStore((s) => s.resumeAudio);
  const pauseAudio = usePlayerStore((s) => s.pauseAudio);
  const stopAudio = usePlayerStore((s) => s.stopAudio);
  const seekAudio = usePlayerStore((s) => s.seekAudio);
  const upgradeInFlightRef = useRef(false);
  const lastVolumeRef = useRef(volume);
  const downloadRequestedRef = useRef(new Set<string>());
  const getPreferredFormats = () => {
    const audio = audioRef.current;
    if (!audio) return { fileFormat: 'm4a', streamFormat: 'm4a' };
    const canMp3 = audio.canPlayType('audio/mpeg');
    const canM4a = audio.canPlayType('audio/mp4');
    const canWebm = audio.canPlayType('audio/webm');
    return {
      fileFormat: canMp3 ? 'mp3' : 'm4a',
      streamFormat: canM4a ? 'm4a' : canWebm ? 'webm' : 'm4a',
    };
  };

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
    const nextVolume = Math.max(0, Math.min(volume, 100));
    if (playbackMode === 'video') {
      if (videoController) {
        videoController.setVolume(nextVolume);
        videoController.setMuted(nextVolume === 0);
      }
      return;
    }
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = nextVolume / 100;
  }, [playbackMode, videoController, volume]);

  useEffect(() => {
    if (volume > 0) {
      lastVolumeRef.current = volume;
    }
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
    if (playbackMode !== 'video' || !videoController) return;
    let interval = 0;
    const tick = () => {
      const nextTime = videoController.getCurrentTime();
      if (Number.isFinite(nextTime)) {
        setCurrentTime(nextTime);
      }
      const nextDuration = videoController.getDuration();
      if (Number.isFinite(nextDuration) && nextDuration > 0) {
        setDuration(nextDuration);
      }
    };
    interval = window.setInterval(tick, 400);
    return () => window.clearInterval(interval);
  }, [playbackMode, setCurrentTime, setDuration, videoController]);

  const requestVideoDownload = useCallback(async (videoId: string) => {
    if (!videoId) return;
    if (downloadRequestedRef.current.has(videoId)) return;
    downloadRequestedRef.current.add(videoId);
    setVideoDownloadState(videoId, 'checking');
    try {
      const { fileFormat, streamFormat } = getPreferredFormats();
      const preferredFormat = streamFormat || fileFormat;
      const primaryStatus = await audio2Api.getYoutubeDownloadStatus(videoId, { format: fileFormat });
      if (primaryStatus.data?.exists) {
        setVideoDownloadState(videoId, 'downloaded');
        setLastDownloadedVideo(videoId);
        return;
      }
      if (streamFormat && streamFormat !== fileFormat) {
        const streamStatus = await audio2Api.getYoutubeDownloadStatus(videoId, { format: streamFormat });
        if (streamStatus.data?.exists) {
          setVideoDownloadState(videoId, 'downloaded');
          setLastDownloadedVideo(videoId);
          return;
        }
      }
      setVideoDownloadState(videoId, 'downloading');
      await audio2Api.downloadYoutubeAudio(videoId, { format: preferredFormat, quality: 'bestaudio' });
      setVideoDownloadState(videoId, 'downloaded');
      setLastDownloadedVideo(videoId);
    } catch (err) {
      console.warn('No se pudo descargar el audio del video', err);
      setVideoDownloadState(videoId, 'error');
      downloadRequestedRef.current.delete(videoId);
    }
  }, [setLastDownloadedVideo, setVideoDownloadState]);

  useEffect(() => {
    if (!videoEmbedId) return;
    void requestVideoDownload(videoEmbedId);
  }, [requestVideoDownload, videoEmbedId]);

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
  }, [audioSourceMode, nowPlaying, playbackMode, tryUpgradeToFile]);

  const formatTime = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return '0:00';
    const mins = Math.floor(value / 60);
    const secs = Math.floor(value % 60);
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const canSeek = playbackMode === 'video' ? !!videoController : audioSourceMode !== 'stream';
  const footerStatus = useMemo(() => {
    if (!nowPlaying) return 'Pausado';
    if (statusMessage) return statusMessage;
    return isPlaying ? 'Reproduciendo' : 'Pausado';
  }, [isPlaying, nowPlaying, statusMessage]);
  const isVideo = playbackMode === 'video';
  const audioDownloadLabel = useMemo(() => {
    if (!nowPlaying?.videoId) return 'pendiente';
    if (audioDownloadVideoId !== nowPlaying.videoId) return 'pendiente';
    if (audioDownloadStatus === 'checking') return 'comprobando';
    if (audioDownloadStatus === 'downloading') return 'descargando';
    if (audioDownloadStatus === 'downloaded') return 'descargado';
    if (audioDownloadStatus === 'error') return 'error';
    return 'pendiente';
  }, [audioDownloadStatus, audioDownloadVideoId, nowPlaying?.videoId]);
  const audioDownloadActive =
    !!nowPlaying?.videoId &&
    audioDownloadVideoId === nowPlaying.videoId &&
    audioDownloadStatus === 'downloading';
  const trackLabel = nowPlaying
    ? `${isVideo ? 'Video' : 'Reproduciendo'}: ${nowPlaying.title} · ${nowPlaying.artist || ''}`
    : isVideo
      ? 'Selecciona una canción para ver el video'
      : 'Selecciona una canción para reproducir';

  const handlePlay = useCallback(() => {
    if (!nowPlaying) return;
    if (playbackMode === 'video') {
      if (!nowPlaying.videoId) return;
      pauseAudio();
      setStatusMessage('');
      if (!videoEmbedId || videoEmbedId !== nowPlaying.videoId) {
        setVideoEmbedId(nowPlaying.videoId);
        setIsPlaying(true);
        return;
      }
      if (videoController) {
        videoController.play();
        setIsPlaying(true);
      } else {
        setStatusMessage('Cargando video...');
      }
      return;
    }
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.src || !audio.src.includes(nowPlaying.videoId)) {
      void playByVideoId(nowPlaying);
      return;
    }
    resumeAudio();
  }, [nowPlaying, playbackMode, pauseAudio, setStatusMessage, videoEmbedId, setVideoEmbedId, setIsPlaying, videoController, playByVideoId, resumeAudio]);

  const handlePause = useCallback(() => {
    if (playbackMode === 'video') {
      if (videoController) {
        videoController.pause();
        setStatusMessage('Video pausado');
      } else {
        setStatusMessage('Video no disponible');
      }
      setIsPlaying(false);
      return;
    }
    pauseAudio();
  }, [playbackMode, videoController, setStatusMessage, setIsPlaying, pauseAudio]);

  const handleStop = useCallback(() => {
    if (playbackMode === 'video') {
      if (videoController) {
        videoController.stop();
      }
      setVideoEmbedId(null);
      setStatusMessage('Video detenido');
      setIsPlaying(false);
      setCurrentTime(0);
      setDuration(0);
      return;
    }
    stopAudio();
  }, [playbackMode, videoController, setVideoEmbedId, setStatusMessage, setIsPlaying, setCurrentTime, setDuration, stopAudio]);

  const handleSeek = useCallback((value: number) => {
    if (playbackMode === 'video') {
      if (!videoController) return;
      videoController.seek(value);
      setCurrentTime(value);
      return;
    }
    seekAudio(value);
  }, [playbackMode, videoController, setCurrentTime, seekAudio]);

  const handlePrev = useCallback(() => {
    if (!prevItem || !onPlayTrack) return;
    onPlayTrack(prevItem);
  }, [prevItem, onPlayTrack]);

  const handleNext = useCallback(() => {
    if (!nextItem || !onPlayTrack) return;
    onPlayTrack(nextItem);
  }, [nextItem, onPlayTrack]);

  useEffect(() => {
    const clampVolume = (value: number) => Math.max(0, Math.min(100, value));

    const seekBy = (delta: number) => {
      if (!nowPlaying) return;
      const base = Number.isFinite(currentTime) ? currentTime : 0;
      const rawTarget = base + delta;
      const target = Math.max(0, rawTarget);
      const bounded = Number.isFinite(duration) && duration > 0 ? Math.min(target, duration) : target;
      handleSeek(bounded);
    };

    const toggleMute = () => {
      const next = volume > 0 ? 0 : Math.max(5, lastVolumeRef.current || 70);
      setVolume(next);
      if (playbackMode === 'video') {
        videoController?.setMuted(next === 0);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) {
        return;
      }
      if (!nowPlaying) return;
      switch (event.code) {
        case 'Space':
        case 'MediaPlayPause':
          event.preventDefault();
          if (isPlaying) {
            handlePause();
          } else {
            handlePlay();
          }
          break;
        case 'ArrowRight':
          event.preventDefault();
          seekBy(5);
          break;
        case 'ArrowLeft':
          event.preventDefault();
          seekBy(-5);
          break;
        case 'ArrowUp':
          event.preventDefault();
          setVolume(clampVolume(volume + 5));
          break;
        case 'ArrowDown':
          event.preventDefault();
          setVolume(clampVolume(volume - 5));
          break;
        case 'KeyM':
          event.preventDefault();
          toggleMute();
          break;
        case 'KeyN':
        case 'MediaTrackNext':
          event.preventDefault();
          handleNext();
          break;
        case 'KeyP':
        case 'MediaTrackPrevious':
          event.preventDefault();
          handlePrev();
          break;
        case 'KeyS':
          event.preventDefault();
          handleStop();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    currentTime,
    duration,
    handleNext,
    handlePause,
    handlePlay,
    handlePrev,
    handleSeek,
    handleStop,
    isPlaying,
    nowPlaying,
    playbackMode,
    setVolume,
    videoController,
    volume,
  ]);

  const renderControls = () => (
    <>
      <div className="album-player__left">
        <button className="album-player__btn" onClick={handlePrev} disabled={!prevItem || !onPlayTrack} title="Anterior">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M19 5L11 12L19 19V5z" />
            <path d="M13 5L5 12L13 19V5z" />
          </svg>
        </button>
        <button
          className="album-player__btn album-player__btn--primary"
          onClick={handlePlay}
          disabled={!nowPlaying}
          title={isVideo ? 'Mostrar video' : 'Reproducir'}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5L19 12L8 19V5z" />
          </svg>
        </button>
        <button className="album-player__btn" onClick={handlePause} disabled={!nowPlaying} title={isVideo ? 'Pausar video' : 'Pausar'}>
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
        <button className="album-player__btn" onClick={handleStop} disabled={!nowPlaying} title={isVideo ? 'Cerrar video' : 'Detener'}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6h12v12H6z" />
          </svg>
        </button>
      </div>
      <div className="album-player__timeline">
        <div className="album-player__track">{trackLabel}</div>
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
            aria-label="Progreso"
          />
          <span className="album-player__time">{formatTime(duration)}</span>
        </div>
      </div>
      <div className="album-player__right">
        <div className="album-player__mode">
          <button className={`album-player__mode-btn ${playbackMode === 'audio' ? 'is-active' : ''}`} onClick={() => setPlaybackMode('audio')} type="button">
            Audio
          </button>
          <button className={`album-player__mode-btn ${playbackMode === 'video' ? 'is-active' : ''}`} onClick={() => setPlaybackMode('video')} type="button">
            Video
          </button>
        </div>
        <div className="album-player__volume">
          <input
            type="range"
            className="album-player__slider album-player__slider--volume"
            min={0}
            max={100}
            value={volume}
            onChange={(event) => setVolume(Number(event.target.value))}
          />
        </div>
        <div className="album-player__status">{footerStatus}</div>
        {!isVideo && nowPlaying && (
          <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: audioDownloadActive ? '#22c55e' : 'transparent',
                border: '2px solid #22c55e',
                display: 'inline-block',
              }}
            />
            <span>Audio: {audioDownloadLabel}</span>
          </div>
        )}
      </div>
      <audio ref={audioRef} hidden />
    </>
  );

  return (
    <footer className="album-player">{renderControls()}</footer>
  );
}
