import { create } from 'zustand';
import { audio2Api, API_BASE_URL } from '@/lib/api';

export type PlaybackMode = 'audio' | 'video';
export type AudioSourceMode = 'file' | 'stream';

export type PlayerTrack = {
  spotifyTrackId: string;
  title: string;
  artist?: string;
  videoId: string;
  durationSec?: number;
};

export type PlayerQueueItem = {
  spotifyTrackId: string;
  title: string;
  artist?: string;
  durationMs?: number;
  videoId?: string;
  rawTrack?: any;
};

type VideoControls = {
  play?: () => void;
  pause?: () => void;
  stop?: () => void;
  seek?: (value: number) => void;
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
  videoControls: VideoControls | null;
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
  setVideoControls: (controls: VideoControls | null) => void;
  playByVideoId: (payload: PlayerTrack) => Promise<{ ok: boolean; mode?: AudioSourceMode }>;
  resumeAudio: () => void;
  pauseAudio: () => void;
  stopAudio: () => void;
  seekAudio: (value: number) => void;
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
  videoControls: null,
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
  setVideoControls: (videoControls) => set({ videoControls }),
  playByVideoId: async (payload) => {
    const audio = get().audioEl;
    if (!audio) return { ok: false };
    set({
      nowPlaying: payload,
      currentTime: 0,
      duration: payload.durationSec || 0,
      statusMessage: 'Abriendo audio...',
    });
    audio.muted = false;
    audio.pause();
    audio.currentTime = 0;
    const { fileFormat, streamFormat } = getFormats(audio);
    const status = await audio2Api
      .getYoutubeDownloadStatus(payload.videoId, { format: fileFormat })
      .catch(() => null);
    if (status?.data?.exists) {
      set({ audioSourceMode: 'file', statusMessage: '' });
      audio.src = `${API_BASE_URL}/youtube/download/${payload.videoId}/file?format=${fileFormat}`;
    } else {
      set({ audioSourceMode: 'stream', statusMessage: 'Streaming...' });
      audio.src = `${API_BASE_URL}/youtube/stream/${payload.videoId}?format=${streamFormat}&cache=true`;
    }
    audio.load();
    try {
      await audio.play();
      return { ok: true, mode: get().audioSourceMode };
    } catch {
      audio.src = '';
      set({ statusMessage: 'No se pudo reproducir el audio' });
      return { ok: false };
    }
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
}));
