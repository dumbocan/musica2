import { create } from 'zustand';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';

export type PlaybackMode = 'audio' | 'video';
export type AudioSourceMode = 'file' | 'stream';
export type VideoController = {
  play: () => void;
  pause: () => void;
  stop: () => void;
  seek: (value: number) => void;
  setVolume: (value: number) => void;
  getVolume: () => number;
  getCurrentTime: () => number;
  getDuration: () => number;
  isMuted: () => boolean;
  setMuted: (muted: boolean) => void;
};

export type VideoDownloadStatus = 'idle' | 'checking' | 'downloading' | 'downloaded' | 'missing' | 'error';

export type PlayerTrack = {
  localTrackId?: number;
  spotifyTrackId: string;
  title: string;
  artist?: string;
  artistSpotifyId?: string;
  videoId: string;
  durationSec?: number;
};

export type RecentPlay = PlayerTrack & {
  playedAt: number;
};

export type PlayerQueueItem = {
  localTrackId?: number;
  spotifyTrackId: string;
  title: string;
  artist?: string;
  artistSpotifyId?: string;
  durationMs?: number;
  videoId?: string;
  rawTrack?: unknown;
};

type PlayerStore = {
  audioEl: HTMLAudioElement | null;
  nowPlaying: PlayerTrack | null;
  queue: PlayerQueueItem[];
  currentIndex: number;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  playbackMode: PlaybackMode;
  audioSourceMode: AudioSourceMode;
  statusMessage: string;
  onPlayTrack: ((item: PlayerQueueItem) => void) | null;
  setAudioEl: (el: HTMLAudioElement | null) => void;
  setNowPlaying: (track: PlayerTrack | null) => void;
  setQueue: (queue: PlayerQueueItem[], currentIndex?: number) => void;
  setCurrentIndex: (index: number) => void;
  setIsPlaying: (isPlaying: boolean) => void;
  setCurrentTime: (value: number) => void;
  setDuration: (value: number) => void;
  setVolume: (value: number) => void;
  setPlaybackMode: (mode: PlaybackMode) => void;
  setAudioSourceMode: (mode: AudioSourceMode) => void;
  setStatusMessage: (message: string) => void;
  setOnPlayTrack: (handler: ((item: PlayerQueueItem) => void) | null) => void;
  videoEmbedId: string | null;
  setVideoEmbedId: (id: string | null) => void;
  videoController: VideoController | null;
  setVideoController: (controller: VideoController | null) => void;
  videoDownloadVideoId: string | null;
  videoDownloadStatus: VideoDownloadStatus;
  setVideoDownloadState: (videoId: string | null, status: VideoDownloadStatus) => void;
  audioDownloadVideoId: string | null;
  audioDownloadStatus: VideoDownloadStatus;
  setAudioDownloadState: (videoId: string | null, status: VideoDownloadStatus) => void;
  lastDownloadedVideo: { videoId: string; ts: number } | null;
  setLastDownloadedVideo: (videoId: string | null) => void;
  recentPlays: RecentPlay[];
  recordRecentPlay: (track: PlayerTrack) => void;
  playByVideoId: (payload: PlayerTrack) => Promise<{ ok: boolean; mode?: AudioSourceMode }>;
  tryUpgradeToFile: () => Promise<boolean>;
  resumeAudio: () => void;
  pauseAudio: () => void;
  stopAudio: () => void;
  seekAudio: (value: number) => void;
  shuffleMode: boolean;
  setShuffleMode: (enabled: boolean) => void;
  crossfadeEnabled: boolean;
  crossfadeMs: number;
  setCrossfadeEnabled: (enabled: boolean) => void;
  setCrossfadeMs: (value: number) => void;
};

const getFormats = (audio: HTMLAudioElement | null) => {
  if (!audio) return { fileFormat: 'm4a', streamFormat: 'm4a' };
  const canMp3 = audio.canPlayType('audio/mpeg');
  const canM4a = audio.canPlayType('audio/mp4');
  const canWebm = audio.canPlayType('audio/webm');
  return {
    fileFormat: canMp3 ? 'mp3' : 'm4a',
    streamFormat: canM4a ? 'm4a' : canWebm ? 'webm' : 'm4a',
  };
};

const crossfadeToSource = async (
  mainAudio: HTMLAudioElement,
  nextSrc: string,
  targetVolume: number,
  durationMs = 1000
): Promise<boolean> => {
  const ghost = new Audio();
  ghost.preload = 'auto';
  ghost.muted = false;
  ghost.volume = 0;
  ghost.src = nextSrc;

  try {
    await ghost.play();
  } catch {
    return false;
  }

  const start = performance.now();
  const initialMainVolume = Number.isFinite(mainAudio.volume) ? mainAudio.volume : targetVolume;
  await new Promise<void>((resolve) => {
    const timer = setInterval(() => {
      const elapsed = performance.now() - start;
      const progress = Math.max(0, Math.min(1, elapsed / durationMs));
      mainAudio.volume = initialMainVolume * (1 - progress);
      ghost.volume = targetVolume * progress;
      if (progress >= 1) {
        clearInterval(timer);
        resolve();
      }
    }, 40);
  });

  const resumeAt = Number.isFinite(ghost.currentTime) ? ghost.currentTime : 0;
  mainAudio.pause();
  mainAudio.src = nextSrc;
  mainAudio.load();
  try {
    if (resumeAt > 0) {
      mainAudio.currentTime = resumeAt;
    }
  } catch {
    // ignore seek errors while media is loading
  }
  mainAudio.volume = targetVolume;
  try {
    await mainAudio.play();
    ghost.pause();
    ghost.src = '';
    return true;
  } catch {
    ghost.pause();
    ghost.src = '';
    return false;
  }
};

const RECENT_PLAYS_KEY = 'audio2_recent_plays';
const MAX_RECENT_PLAYS = 20;
const CROSSFADER_ENABLED_KEY = 'audio2_crossfade_enabled';
const CROSSFADER_MS_KEY = 'audio2_crossfade_ms';

const loadRecentPlays = (): RecentPlay[] => {
  try {
    const raw = localStorage.getItem(RECENT_PLAYS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) =>
      item && typeof item === 'object' && typeof item.videoId === 'string' && typeof item.title === 'string'
    );
  } catch {
    return [];
  }
};

const persistRecentPlays = (plays: RecentPlay[]) => {
  try {
    localStorage.setItem(RECENT_PLAYS_KEY, JSON.stringify(plays));
  } catch {
    // ignore storage errors
  }
};

const loadCrossfadeEnabled = (): boolean => {
  try {
    const raw = localStorage.getItem(CROSSFADER_ENABLED_KEY);
    return raw === null ? true : raw === 'true';
  } catch {
    return true;
  }
};

const loadCrossfadeMs = (): number => {
  try {
    const raw = localStorage.getItem(CROSSFADER_MS_KEY);
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return 1000;
    return Math.max(0, Math.min(4000, Math.round(parsed)));
  } catch {
    return 1000;
  }
};

export const usePlayerStore = create<PlayerStore>((set, get) => ({
  audioEl: null,
  nowPlaying: null,
  queue: [],
  currentIndex: -1,
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  volume: 70,
  playbackMode: 'audio',
  audioSourceMode: 'file',
  statusMessage: '',
  onPlayTrack: null,
  setAudioEl: (audioEl) => set({ audioEl }),
  setNowPlaying: (nowPlaying) => set({ nowPlaying }),
  setQueue: (queue, currentIndex) =>
    set({
      queue,
      currentIndex: Number.isFinite(currentIndex ?? -1) ? (currentIndex as number) : get().currentIndex,
    }),
  setCurrentIndex: (currentIndex) => set({ currentIndex }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setCurrentTime: (currentTime) => set({ currentTime }),
  setDuration: (duration) => set({ duration }),
  setVolume: (volume) => set({ volume }),
  setPlaybackMode: (playbackMode) => set({ playbackMode }),
  setAudioSourceMode: (audioSourceMode) => set({ audioSourceMode }),
  setStatusMessage: (statusMessage) => set({ statusMessage }),
  setOnPlayTrack: (onPlayTrack) => set({ onPlayTrack }),
  videoEmbedId: null,
  setVideoEmbedId: (videoEmbedId) => set({ videoEmbedId }),
  videoController: null,
  setVideoController: (videoController) => set({ videoController }),
  videoDownloadVideoId: null,
  videoDownloadStatus: 'idle',
  setVideoDownloadState: (videoDownloadVideoId, videoDownloadStatus) =>
    set({ videoDownloadVideoId, videoDownloadStatus }),
  audioDownloadVideoId: null,
  audioDownloadStatus: 'idle',
  setAudioDownloadState: (audioDownloadVideoId, audioDownloadStatus) =>
    set({ audioDownloadVideoId, audioDownloadStatus }),
  lastDownloadedVideo: null,
  setLastDownloadedVideo: (videoId) =>
    set({ lastDownloadedVideo: videoId ? { videoId, ts: Date.now() } : null }),
  recentPlays: loadRecentPlays(),
  recordRecentPlay: (track) => {
    const key = `${track.spotifyTrackId}|${track.videoId}`;
    set((state) => {
      const next = [
        { ...track, playedAt: Date.now() },
        ...state.recentPlays.filter((item) => `${item.spotifyTrackId}|${item.videoId}` !== key),
      ].slice(0, MAX_RECENT_PLAYS);
      persistRecentPlays(next);
      return { recentPlays: next };
    });
  },
  playByVideoId: async (payload) => {
    const audio = get().audioEl;
    if (!audio) return { ok: false };
    const token = useApiStore.getState().token;
    const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    const isLocalSynthetic = payload.videoId.startsWith('local:');
    set({
      nowPlaying: payload,
      currentTime: 0,
      duration: payload.durationSec || 0,
      statusMessage: 'Abriendo audio...',
      audioDownloadVideoId: payload.videoId,
      audioDownloadStatus: 'checking',
    });
    audio.muted = false;
    const { fileFormat, streamFormat } = getFormats(audio);
    const targetVolume = Math.max(0, Math.min(get().volume, 100)) / 100;
    let nextSrc = '';
    let nextAudioMode: AudioSourceMode = 'stream';

    // DB-FIRST: Check if track has local file in DB
    let localFilePath: string | null = null;
    let dbYoutubeVideoId: string | null = null;

    if (payload.localTrackId) {
      try {
        const downloadInfo = await audio2Api.getTrackDownloadInfo(payload.localTrackId);
        if (downloadInfo.data?.local_file_exists && downloadInfo.data?.local_file_path) {
          localFilePath = downloadInfo.data.local_file_path;
        }
        if (downloadInfo.data?.youtube_video_id) {
          dbYoutubeVideoId = downloadInfo.data.youtube_video_id;
        }
      } catch {
        // Ignore errors, fall back to YouTube check
      }
    }

    // Use local file if found in DB
    if (localFilePath) {
      nextAudioMode = 'file';
      set({ audioSourceMode: 'file', statusMessage: '', audioDownloadStatus: 'downloaded' });
      if (payload.localTrackId) {
        nextSrc = `${API_BASE_URL}/youtube/download/by-local-track/${payload.localTrackId}/file${tokenQuery}`;
      } else if (payload.spotifyTrackId && /^[A-Za-z0-9]{22}$/.test(payload.spotifyTrackId)) {
        nextSrc = `${API_BASE_URL}/youtube/download/by-track/${encodeURIComponent(payload.spotifyTrackId)}/file${tokenQuery}`;
      } else {
        const videoIdForDownload = dbYoutubeVideoId || payload.videoId;
        nextSrc = `${API_BASE_URL}/youtube/download/${videoIdForDownload}/file?format=${fileFormat}${tokenParam}`;
      }
    } else {
      if (isLocalSynthetic) {
        set({ audioSourceMode: 'stream', statusMessage: 'Archivo local no encontrado en BD', audioDownloadStatus: 'error' });
        audio.src = '';
        return { ok: false };
      }
      // Fall back to checking YouTube downloads folder
      const candidateFormats = Array.from(new Set([fileFormat, 'm4a', 'mp3', 'webm']));
      let localFormat: string | null = null;
      for (const fmt of candidateFormats) {
        const status = await audio2Api
          .getYoutubeDownloadStatus(payload.videoId, { format: fmt })
          .catch(() => null);
        if (status?.data?.exists) {
          localFormat = fmt;
          break;
        }
      }
      if (localFormat) {
        nextAudioMode = 'file';
        set({ audioSourceMode: 'file', statusMessage: '', audioDownloadStatus: 'downloaded' });
        nextSrc = `${API_BASE_URL}/youtube/download/${payload.videoId}/file?format=${localFormat}${tokenParam}`;
      } else {
        nextAudioMode = 'stream';
        set({ audioSourceMode: 'stream', statusMessage: 'Streaming...', audioDownloadStatus: 'downloading' });
        nextSrc = `${API_BASE_URL}/youtube/stream/${payload.videoId}?format=${streamFormat}&cache=true${tokenParam}`;
      }
    }

    const { crossfadeEnabled, crossfadeMs } = get();
    const shouldCrossfade =
      crossfadeEnabled &&
      crossfadeMs > 0 &&
      !audio.paused &&
      !!audio.src &&
      !!nextSrc &&
      audio.src !== nextSrc &&
      get().playbackMode === 'audio';

    try {
      if (shouldCrossfade) {
        const faded = await crossfadeToSource(audio, nextSrc, targetVolume, crossfadeMs);
        if (!faded) {
          audio.pause();
          audio.currentTime = 0;
          audio.src = nextSrc;
          audio.load();
          await audio.play();
        }
      } else {
        audio.pause();
        audio.currentTime = 0;
        audio.src = nextSrc;
        audio.load();
        await audio.play();
      }
      set({ audioSourceMode: nextAudioMode });
      get().recordRecentPlay(payload);
      const recordBackendPlay = async () => {
        let trackId = payload.localTrackId;
        if (!trackId && /^[A-Za-z0-9]{22}$/.test(payload.spotifyTrackId)) {
          const resolved = await audio2Api
            .resolveTracks([payload.spotifyTrackId])
            .catch(() => null);
          const resolvedId = resolved?.data?.items?.[0]?.track_id;
          if (typeof resolvedId === 'number') {
            trackId = resolvedId;
          }
        }
        if (trackId) {
          await audio2Api.recordTrackPlay(trackId).catch(() => null);
        }
      };
      void recordBackendPlay();
      return { ok: true, mode: get().audioSourceMode };
    } catch {
      audio.src = '';
      set({ statusMessage: 'No se pudo reproducir el audio', audioDownloadStatus: 'error' });
      return { ok: false };
    }
  },
  tryUpgradeToFile: async () => {
    const { nowPlaying, audioSourceMode, audioEl } = get();
    if (!nowPlaying || audioSourceMode !== 'stream' || !audioEl) return false;
    const { fileFormat } = getFormats(audioEl);
    const status = await audio2Api
      .getYoutubeDownloadStatus(nowPlaying.videoId, { format: fileFormat })
      .catch(() => null);
    if (!status?.data?.exists) return false;
    const token = useApiStore.getState().token;
    const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';
    set({
      audioDownloadStatus: 'downloaded',
      lastDownloadedVideo: { videoId: nowPlaying.videoId, ts: Date.now() },
    });
    if (!audioEl.paused && Number.isFinite(audioEl.currentTime) && audioEl.currentTime > 1) {
      return false;
    }
    const resumeTime = Number.isFinite(audioEl.currentTime) ? audioEl.currentTime : 0;
    const wasPlaying = !audioEl.paused;
    set({ audioSourceMode: 'file', statusMessage: '', audioDownloadStatus: 'downloaded' });
    audioEl.src = `${API_BASE_URL}/youtube/download/${nowPlaying.videoId}/file?format=${fileFormat}${tokenParam}`;
    const handleLoaded = () => {
      audioEl.removeEventListener('loadedmetadata', handleLoaded);
      if (resumeTime > 0) {
        try {
          audioEl.currentTime = resumeTime;
        } catch {
          // ignore seek errors on load
        }
      }
      if (wasPlaying) {
        void audioEl.play();
      }
    };
    audioEl.addEventListener('loadedmetadata', handleLoaded);
    audioEl.load();
    return true;
  },
  resumeAudio: () => {
    const audio = get().audioEl;
    if (!audio) return;
    void audio.play();
  },
  pauseAudio: () => {
    const audio = get().audioEl;
    if (!audio) return;
    audio.pause();
  },
  stopAudio: () => {
    const audio = get().audioEl;
    if (!audio) return;
    audio.pause();
    audio.currentTime = 0;
    set({ currentTime: 0, isPlaying: false });
  },
  seekAudio: (value) => {
    if (get().audioSourceMode === 'stream') return;
    const audio = get().audioEl;
    if (!audio) return;
    audio.currentTime = value;
    set({ currentTime: value });
  },
  shuffleMode: false,
  setShuffleMode: (shuffleMode) => set({ shuffleMode }),
  crossfadeEnabled: loadCrossfadeEnabled(),
  crossfadeMs: loadCrossfadeMs(),
  setCrossfadeEnabled: (enabled) => {
    set({ crossfadeEnabled: enabled });
    try {
      localStorage.setItem(CROSSFADER_ENABLED_KEY, String(enabled));
    } catch {
      // ignore storage errors
    }
  },
  setCrossfadeMs: (value) => {
    const next = Math.max(0, Math.min(4000, Math.round(value)));
    set({ crossfadeMs: next });
    try {
      localStorage.setItem(CROSSFADER_MS_KEY, String(next));
    } catch {
      // ignore storage errors
    }
  },
}));
