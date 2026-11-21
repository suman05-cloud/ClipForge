import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  CheckCircle2,
  ChevronRight,
  Clapperboard,
  Download,
  Film,
  FolderOpen,
  Grid,
  HardDrive,
  LoaderCircle,
  Monitor,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Scissors,
  Play,
  Pause,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
  Cpu,
  Layers,
  Link2
} from 'lucide-react';
import type { Clip, Export, Health, Job, Project, Segment, Analysis } from './types';

const API = '/api';
const time = (s: number) => {
  const n = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(n / 60).toString().padStart(2, '0')}:${(n % 60).toString().padStart(2, '0')}`;
};
const bytes = (n: number) => n > 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GB` : `${(n / 1024 ** 2).toFixed(1)} MB`;

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const value = await res.json();
      message = typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail || value);
    } catch {
      /* retain status */
    }
    throw new Error(message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const defaults = (duration: number): Omit<Clip, 'id'> => ({
  title: 'Untitled clip',
  start: 0,
  end: Math.min(30, duration),
  aspect: '9:16',
  fit: 'crop',
  crop_x: 0.5,
  crop_y: 0.5,
  zoom: 1,
  caption_style: 'bold',
  font_size: 48,
  caption_color: '#ffffff',
  accent_color: '#c9a37e',
  burn_captions: true
});

const clipPayload = (clip: Clip) => ({
  title: clip.title,
  start: clip.start,
  end: clip.end,
  aspect: clip.aspect,
  fit: clip.fit,
  crop_x: clip.crop_x,
  crop_y: clip.crop_y ?? 0.5,
  zoom: clip.zoom ?? 1,
  caption_style: clip.caption_style,
  font_size: clip.font_size,
  caption_color: clip.caption_color,
  accent_color: clip.accent_color,
  burn_captions: clip.burn_captions
});

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadModalTab, setUploadModalTab] = useState<'file' | 'link'>('file');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkTitle, setLinkTitle] = useState('');
  const [linkFetchSubs, setLinkFetchSubs] = useState(true);
  const [linkCookies, setLinkCookies] = useState<'none' | 'chrome' | 'edge'>('none');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [drag, setDrag] = useState(false);
  const [section, setSection] = useState<'library' | 'exports'>('library');
  const [tab, setTab] = useState<'clips' | 'transcript' | 'exports'>('clips');
  const [clip, setClip] = useState<Clip | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [dirtyClip, setDirtyClip] = useState(false);
  const [dirtyTranscript, setDirtyTranscript] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [resolution, setResolution] = useState(720);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [provider, setProvider] = useState<'heuristic' | 'ollama'>('ollama');
  const [model, setModel] = useState('qwen3.5:9b');
  const [minDuration, setMinDuration] = useState(15);
  const [maxDuration, setMaxDuration] = useState(60);
  const [count, setCount] = useState(5);
  const [transcribeOpen, setTranscribeOpen] = useState(false);
  const [whisperModel, setWhisperModel] = useState('base.en');
  const [language, setLanguage] = useState('');
  const [allowDownload, setAllowDownload] = useState(false);
  const [device, setDevice] = useState<'auto' | 'cuda' | 'cpu'>('auto');
  const [cpuThreads, setCpuThreads] = useState(8);
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ loaded: number; total: number; stage: 'uploading' | 'preparing' } | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showCropGrid, setShowCropGrid] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const frame = useRef<HTMLDivElement>(null);
  const [frameSize, setFrameSize] = useState({ width: 360, height: 640 });
  const cropDrag = useRef<{ x: number; y: number; cropX: number; cropY: number } | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const transcriptInput = useRef<HTMLInputElement>(null);
  const activeProject = useRef<string | null>(null);
  const draftState = useRef({ clip: false, transcript: false });
  draftState.current = { clip: dirtyClip, transcript: dirtyTranscript };

  const loadProjects = useCallback(async () => {
    const data = await api<Project[]>('/projects');
    setProjects(data);
  }, []);

  const refreshProject = useCallback(async (id: string, keepClip = true) => {
    const p = await api<Project>(`/projects/${id}`);
    p.clips ||= [];
    p.segments ||= [];
    p.exports ||= [];
    if (activeProject.current === id) {
      setProject(p);
      if (p.active_job && ['queued', 'running'].includes(p.active_job.status)) setJob(p.active_job);
      if (!keepClip || !draftState.current.transcript) {
        setSegments(p.segments);
        setDirtyTranscript(false);
      }
      if (!keepClip || !draftState.current.clip) {
        setClip((old) => (keepClip && old ? p.clips.find((c) => c.id === old.id) || p.clips[0] || null : p.clips[0] || null));
        setDirtyClip(false);
      }
    }
    await loadProjects();
    return p;
  }, [loadProjects]);

  useEffect(() => {
    Promise.all([
      loadProjects(),
      api<Health>('/health').then((h) => {
        setHealth(h);
        if (h.default_model) setModel(h.default_model);
        if (h.transcription_cpu_threads) setCpuThreads(h.transcription_cpu_threads);
        if (h.transcription_cached_models?.length) setWhisperModel(h.transcription_cached_models[0]);
        if (h.transcription_gpu_available) setDevice('auto');
      })
    ])
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [loadProjects]);

  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(''), 5000);
    return () => clearTimeout(id);
  }, [notice]);

  // Dynamic fast polling for real-time progress bars
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    let cancelled = false;
    const pollInterval = job.status === 'running' ? 400 : 1000;
    const id = setInterval(async () => {
      try {
        const next = await api<Job>(`/jobs/${job.id}`);
        if (cancelled) return;
        setJob(next);
        if (next.status === 'completed') {
          clearInterval(id);
          setNotice(next.message || 'Completed successfully');
          if (next.project_id) {
            activeProject.current = next.project_id;
            await refreshProject(next.project_id, false);
          } else if (activeProject.current) {
            await refreshProject(activeProject.current);
          } else {
            await loadProjects();
          }
        }
        if (next.status === 'failed') {
          clearInterval(id);
          setError(next.error || next.message || 'The job failed.');
        }
      } catch (e) {
        if (!cancelled) setError(`Could not refresh job status. ${(e as Error).message}`);
      }
    }, pollInterval);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [job?.id, job?.status, refreshProject, loadProjects]);

  useEffect(() => {
    if (!job) return;
    if (!['queued', 'running'].includes(job.status)) {
      localStorage.removeItem('clipforge-active-job');
      return;
    }
    localStorage.setItem('clipforge-active-job', JSON.stringify({ id: job.id, project_id: job.project_id || activeProject.current }));
    const interval = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [job?.id, job?.status]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('clipforge-active-job') || 'null');
      if (saved?.id) api<Job>(`/jobs/${saved.id}`).then(setJob).catch(() => localStorage.removeItem('clipforge-active-job'));
    } catch {
      localStorage.removeItem('clipforge-active-job');
    }
  }, []);

  useEffect(() => {
    const element = frame.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0].contentRect;
      setFrameSize({ width: box.width, height: box.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [project?.id, clip?.aspect]);

  const working = Boolean(busy) || Boolean(job && ['queued', 'running'].includes(job.status));
  const act = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  };

  const openProject = (id: string) =>
    act('Opening project', async () => {
      activeProject.current = id;
      setTab('clips');
      await refreshProject(id, false);
      setCurrentTime(0);
    });

  const home = () => {
    if ((dirtyClip || dirtyTranscript) && !confirm('Discard your unsaved edits?')) return;
    activeProject.current = null;
    setProject(null);
    setClip(null);
    setDirtyClip(false);
    setDirtyTranscript(false);
  };

  const selectClip = (c: Clip) => {
    if (dirtyClip && !confirm('Discard unsaved clip changes?')) return;
    setClip({ ...c });
    setDirtyClip(false);
    if (video.current) video.current.currentTime = c.start;
    setCurrentTime(c.start);
  };

  const updateClip = <K extends keyof Clip>(key: K, value: Clip[K]) => {
    setClip((c) => (c ? { ...c, [key]: value } : c));
    setDirtyClip(true);
  };

  const validateClip = () => {
    if (!clip || !project) throw new Error('Select a clip first.');
    if (!clip.title.trim()) throw new Error('Give this clip a title.');
    if (!Number.isFinite(clip.start) || !Number.isFinite(clip.end) || clip.start < 0 || clip.end <= clip.start || clip.end > project.duration + 0.01)
      throw new Error('Clip end must be after its start and within the source video.');
  };

  const saveClip = async () => {
    validateClip();
    const saved = await api<Clip>(`/projects/${project!.id}/clips/${clip!.id}`, {
      method: 'PUT',
      body: JSON.stringify(clipPayload(clip!))
    });
    setClip(saved);
    setDirtyClip(false);
    draftState.current.clip = false;
    setProject((p) => (p ? { ...p, clips: p.clips.map((c) => (c.id === saved.id ? saved : c)) } : p));
  };

  const newClip = () =>
    act('Creating clip', async () => {
      if (!project) return;
      if (dirtyClip && !confirm('Discard unsaved clip changes and create a new clip?')) return;
      const c = await api<Clip>(`/projects/${project.id}/clips`, {
        method: 'POST',
        body: JSON.stringify({ ...defaults(project.duration), title: `Clip ${project.clips.length + 1}` })
      });
      draftState.current.clip = false;
      setDirtyClip(false);
      await refreshProject(project.id);
      setClip(c);
      if (video.current) video.current.currentTime = c.start;
    });

  const upload = () =>
    act('Uploading video', async () => {
      if (!uploadFile) throw new Error('Choose a video first.');
      const form = new FormData();
      form.append('file', uploadFile);
      if (uploadTitle.trim()) form.append('title', uploadTitle.trim());
      setUploadProgress({ loaded: 0, total: uploadFile.size, stage: 'uploading' });

      let p: Project;
      try {
        p = await new Promise<Project>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open('POST', `${API}/projects`);
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              setUploadProgress({
                loaded: e.loaded,
                total: e.total,
                stage: e.loaded >= e.total ? 'preparing' : 'uploading'
              });
            }
          };
          xhr.upload.onload = () => {
            setBusy('Preparing video');
            setUploadProgress((v) => (v ? { ...v, loaded: v.total, stage: 'preparing' } : v));
          };
          xhr.onload = () => {
            let data;
            try {
              data = JSON.parse(xhr.responseText);
            } catch {
              reject(new Error('The server returned an unreadable upload response.'));
              return;
            }
            if (xhr.status >= 200 && xhr.status < 300) resolve(data);
            else reject(new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data)));
          };
          xhr.onerror = () => reject(new Error('Upload connection failed. Check that the local server is running.'));
          xhr.onabort = () => reject(new Error('Upload was cancelled.'));
          xhr.send(form);
        });
      } finally {
        setUploadProgress(null);
      }
      activeProject.current = p.id;
      await refreshProject(p.id, false);
      setUploadOpen(false);
      setUploadFile(null);
      setUploadTitle('');
      setTab('clips');
      setSection('library');
      setNotice('Video imported successfully. Create a clip or add a transcript to find highlights.');
    });

  const importLink = () =>
    act('Connecting to video link', async () => {
      if (!linkUrl.trim()) throw new Error('Please enter a video URL (e.g. YouTube).');
      const j = await api<Job>('/projects/link', {
        method: 'POST',
        body: JSON.stringify({
          url: linkUrl.trim(),
          title: linkTitle.trim() || undefined,
          fetch_subtitles: linkFetchSubs,
          cookies_browser: linkCookies === 'none' ? undefined : linkCookies
        })
      });
      setJob(j);
      if (j.project_id) {
        activeProject.current = j.project_id;
      }
      setUploadOpen(false);
      setLinkUrl('');
      setLinkTitle('');
      setTab('clips');
      setSection('library');
      setNotice('Connecting to video link. Subtitles and preview proxy are being extracted…');
    });

  const addTranscript = (file: File) =>
    act('Importing captions', async () => {
      if (!project) return;
      if (dirtyTranscript && !confirm('Replace your unsaved transcript edits with the imported captions?')) return;
      const data = new FormData();
      data.append('file', file);
      await api(`/projects/${project.id}/transcript/import`, { method: 'POST', body: data });
      draftState.current.transcript = false;
      await refreshProject(project.id);
      setNotice('Captions imported successfully');
    });

  const saveTranscript = () =>
    act('Saving transcript', async () => {
      if (!project) return;
      if (
        segments.some(
          (s) => !s.text.trim() || !Number.isFinite(s.start) || !Number.isFinite(s.end) || s.start < 0 || s.end <= s.start || s.end > project.duration + 0.01
        )
      )
        throw new Error('Each caption needs text and valid start/end times within the video.');
      await api(`/projects/${project.id}/transcript`, { method: 'PUT', body: JSON.stringify({ segments }) });
      draftState.current.transcript = false;
      await refreshProject(project.id);
      setNotice('Transcript saved');
    });

  const allExports = projects.flatMap((p) => (p.exports || []).map((e) => ({ ...e, project: p.title })));
  const currentCaption = (() => {
    const s = segments.find((seg) => currentTime >= seg.start && currentTime < seg.end);
    if (!s || !s.text || !s.text.trim()) return null;
    const words = s.text.trim().split(/\s+/);
    if (words.length <= 5) return words.join(' ');
    // Split into 4-word timed chunks matching the exact playback second (TikTok/Reels format)
    const chunkSize = 4;
    const chunkCount = Math.ceil(words.length / chunkSize);
    const duration = Math.max(0.2, s.end - s.start);
    const relTime = Math.max(0, currentTime - s.start);
    const activeIndex = Math.min(chunkCount - 1, Math.floor((relTime / duration) * chunkCount));
    return words.slice(activeIndex * chunkSize, (activeIndex + 1) * chunkSize).join(' ');
  })();
  const exported = project?.exports || [];

  const scale = project ? Math.max(frameSize.width / project.width, frameSize.height / project.height) * (clip?.zoom ?? 1) : 1;
  const sourceWidth = (project?.width || 1) * scale;
  const sourceHeight = (project?.height || 1) * scale;
  const videoStyle: CSSProperties =
    clip?.fit === 'crop'
      ? {
          position: 'absolute',
          width: sourceWidth,
          height: sourceHeight,
          maxWidth: 'none',
          left: -(sourceWidth - frameSize.width) * (clip.crop_x ?? 0.5),
          top: -(sourceHeight - frameSize.height) * (clip.crop_y ?? 0.5),
          objectFit: 'fill'
        }
      : { width: '100%', height: '100%', objectFit: 'contain' };

  const startStamp = job?.started_at || job?.created_at;
  const elapsed = startStamp ? Math.max(0, Math.floor((clock - Date.parse(startStamp)) / 1000)) : 0;

  const uploadPct = uploadProgress ? Math.round((uploadProgress.loaded / Math.max(1, uploadProgress.total)) * 100) : 0;
  const uploadStatus = uploadProgress && (
    <div className="upload-progress" role="status">
      <div>
        <strong>{uploadProgress.stage === 'preparing' ? 'Preparing video & generating thumbnail' : 'Uploading video file'}</strong>
        <span>{uploadProgress.stage === 'preparing' ? 'Processing…' : `${uploadPct}% (${bytes(uploadProgress.loaded)} / ${bytes(uploadProgress.total)})`}</span>
      </div>
      <div
        className={`progress ${uploadProgress.stage === 'preparing' ? 'indeterminate' : ''}`}
        role="progressbar"
        aria-label="Upload progress"
        aria-valuenow={uploadProgress.stage === 'uploading' ? uploadPct : undefined}
      >
        <span style={{ width: uploadProgress.stage === 'uploading' ? `${uploadPct}%` : undefined }} />
      </div>
      <small>
        {uploadProgress.stage === 'preparing'
          ? 'Upload complete. Extracting video metadata and generating high-res thumbnail…'
          : `${uploadPct}% uploaded · Transferring directly to your local ClipForge folder`}
      </small>
    </div>
  );

  const modal = (title: string, body: React.ReactNode, close: () => void, wide = false) => (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !working) close();
      }}
    >
      <section className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="Close dialog" onClick={close} disabled={working}>
            <X size={20} />
          </button>
        </header>
        {error && (
          <div className="alert error modal-error" role="alert">
            {error}
          </div>
        )}
        {body}
      </section>
    </div>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            home();
          }}
        >
          <span className="brand-symbol">
            <Scissors size={22} />
          </span>
          <span>
            clipforge
            <span className="brand-sub">STUDIO</span>
          </span>
        </a>
        <div className="workspace-label">
          LOCAL WORKSPACE <span className="tiny-tag">OFFLINE</span>
        </div>
        <nav>
          <button className={!project && section === 'library' ? 'nav-item active' : 'nav-item'} onClick={() => { home(); setSection('library'); }}>
            <FolderOpen size={18} /> Video library <span>{projects.length}</span>
          </button>
          <button className={!project && section === 'exports' ? 'nav-item active' : 'nav-item'} onClick={() => { home(); setSection('exports'); }}>
            <ArrowDownToLine size={18} /> Finished clips <span>{allExports.length}</span>
          </button>
          <button className="nav-item" onClick={() => setSettingsOpen(true)}>
            <Settings2 size={18} /> AI & Hardware
          </button>
        </nav>
        <button className="button primary sidebar-upload" onClick={() => setUploadOpen(true)} disabled={working}>
          <Plus size={18} /> New video
        </button>
        <div className="sidebar-bottom">
          <div className="local-note">
            <ShieldCheck size={19} />
            <div>
              <strong>100% Local & Private</strong>
              <p>All video rendering and AI models run locally on your laptop GPU.</p>
            </div>
          </div>
          <div className="profile">
            <span className="avatar">CP</span>
            <div>
              <strong>ClipForge Studio</strong>
              <small>{health?.gpu_name ? 'NVIDIA GPU Accelerated' : 'Local Fast Mode'}</small>
            </div>
            <span className={`status-dot ${health ? 'online' : ''}`} />
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{project ? project.title : section === 'library' ? 'Video library' : 'Exports'}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-badge">
              <span className="status-dot online" /> {health?.gpu_name || 'Laptop GPU + 8 CPU threads ready'}
            </span>
            <button className="icon-button" aria-label="Open settings" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={18} />
            </button>
          </div>
        </header>

        {error && (
          <div className="alert error" role="alert">
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError('')}>
              <X size={17} />
            </button>
          </div>
        )}
        {notice && (
          <div className="alert success" role="status">
            <CheckCircle2 size={18} />
            <span>{notice}</span>
            <button aria-label="Dismiss message" onClick={() => setNotice('')}>
              <X size={17} />
            </button>
          </div>
        )}

        {/* Dynamic Percentage Job Progress Bar */}
        {job && ['queued', 'running'].includes(job.status) && (
          <div className="job-bar" role="status">
            <LoaderCircle size={24} className="spin" />
            <div>
              <div className="job-title">
                <strong>{job.message || 'Processing video task…'}</strong>
                <span>{job.status === 'queued' ? 'Queued' : `${time(elapsed)} elapsed`}</span>
              </div>
              <div className="progress" role="progressbar" aria-label="Processing progress" aria-valuenow={job.progress}>
                <span style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }} />
              </div>
              <small>Dynamic real-time progress powered by faster-whisper and local worker.</small>
            </div>
            <b>{Math.round(job.progress)}%</b>
          </div>
        )}

        {loading ? (
          <div className="loading">
            <LoaderCircle className="spin" size={28} /> Opening your studio…
          </div>
        ) : !project ? (
          <div className="library-page">
            <div className="page-heading">
              <div>
                <div className="eyebrow">WORKSPACE OVERVIEW</div>
                <h1>{section === 'library' ? 'Your video library' : 'Finished video exports'}</h1>
                <p>{section === 'library' ? 'Upload video, crop & frame for social media, transcribe with GPU, and export.' : 'Exported MP4 clips, rendered with subtitles and ready to share.'}</p>
              </div>
              <button className="button primary" onClick={() => setUploadOpen(true)} disabled={working}>
                <Plus size={18} /> Upload video
              </button>
            </div>

            {section === 'library' && (
              <>
                <div className="overview">
                  <div>
                    <Film size={22} />
                    <strong>{projects.length}</strong>
                    <span>Source videos</span>
                  </div>
                  <div>
                    <Scissors size={22} />
                    <strong>{projects.reduce((a, p) => a + (p.clips?.length || 0), 0)}</strong>
                    <span>Clips created</span>
                  </div>
                  <div>
                    <ArrowDownToLine size={22} />
                    <strong>{allExports.length}</strong>
                    <span>Rendered exports</span>
                  </div>
                  <div className="overview-note">
                    <span className="status-dot online" /> Direct local storage · No watermark
                  </div>
                </div>

                <div className="section-heading">
                  <h2>
                    Video recordings <span>{projects.length}</span>
                  </h2>
                  <span className="muted">Your original source recordings</span>
                </div>

                {projects.length ? (
                  <div className="project-grid">
                    {projects.map((p) => (
                      <article className="project-card" key={p.id}>
                        <button className="project-cover" onClick={() => openProject(p.id)} disabled={working}>
                          {p.thumbnail_url ? <img src={p.thumbnail_url} alt="" /> : <Film size={44} />}
                          <span className="duration">{time(p.duration)}</span>
                          {p.is_link && (
                            <span className="source-tag">
                              <Link2 size={10} /> Link
                            </span>
                          )}
                          <span className="cover-play">
                            <Scissors size={24} />
                          </span>
                        </button>
                        <div className="project-info">
                          <button onClick={() => openProject(p.id)} disabled={working}>
                            <h3>{p.title}</h3>
                          </button>
                          <p>
                            {p.width} × {p.height}
                            <span>·</span>
                            {p.clips?.length || 0} clips
                          </p>
                          <footer>
                            <span>{new Date(p.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                            <button
                              className="icon-button danger-on-hover"
                              aria-label={`Delete ${p.title}`}
                              disabled={working}
                              onClick={() => {
                                if (confirm(`Delete “${p.title}” and all its clips and exports?`)) {
                                  act('Deleting project', async () => {
                                    await api(`/projects/${p.id}`, { method: 'DELETE' });
                                    await loadProjects();
                                  });
                                }
                              }}
                            >
                              <Trash2 size={16} />
                            </button>
                          </footer>
                        </div>
                      </article>
                    ))}
                    <button className="add-card" onClick={() => setUploadOpen(true)} disabled={working}>
                      <Plus size={32} />
                      <strong>Add another video</strong>
                      <span>MP4, MOV, WebM, MKV and more</span>
                    </button>
                  </div>
                ) : (
                  <div
                    className={`empty-studio ${drag ? 'drag' : ''}`}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDrag(true);
                    }}
                    onDragLeave={() => setDrag(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDrag(false);
                      setUploadFile(e.dataTransfer.files[0] || null);
                      setUploadOpen(true);
                    }}
                  >
                    <div className="empty-art">
                      <div className="film-frame behind">
                        <span />
                        <span />
                        <span />
                      </div>
                      <div className="film-frame front">
                        <span className="frame-play">
                          <Film size={36} />
                        </span>
                        <div className="art-caption">NEW PROJECT</div>
                      </div>
                    </div>
                    <div className="empty-copy">
                      <span className="eyebrow">FAST LOCAL EDITOR</span>
                      <h2>Start with a video</h2>
                      <p>Upload a video to cut viral short clips, transcribe with your laptop GPU (RTX 4050), and frame in vertical 9:16 or square.</p>
                      <button className="button primary" onClick={() => setUploadOpen(true)}>
                        <Upload size={18} /> Upload your first video <ArrowRight size={18} />
                      </button>
                      <small>or drag and drop a video file here · MP4, MOV, WebM</small>
                    </div>
                  </div>
                )}

                <div className="workflow-strip">
                  <div>
                    <span>01</span>
                    <div>
                      <strong>Upload video</strong>
                      <p>Start with any local recording.</p>
                    </div>
                  </div>
                  <ArrowRight size={18} />
                  <div>
                    <span>02</span>
                    <div>
                      <strong>Transcribe & find moments</strong>
                      <p>GPU Whisper + Ollama Qwen3.5 9B research.</p>
                    </div>
                  </div>
                  <ArrowRight size={18} />
                  <div>
                    <span>03</span>
                    <div>
                      <strong>Crop & Export</strong>
                      <p>9:16, 1:1, 4:5 crop with burn-in captions.</p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {section === 'exports' &&
              (allExports.length ? (
                <div className="export-grid">
                  {allExports.map((e) => (
                    <ExportCard key={e.id} item={e} subtitle={e.project} />
                  ))}
                </div>
              ) : (
                <div className="simple-empty">
                  <Download size={40} />
                  <h2>No exported clips yet</h2>
                  <p>Open a video, create a clip, adjust framing, and export your first MP4.</p>
                  <button className="button primary" onClick={() => setSection('library')}>
                    Go to video library <ArrowRight size={16} />
                  </button>
                </div>
              ))}
          </div>
        ) : (
          <div className="studio-page">
            <div className="studio-heading">
              <button className="icon-button" aria-label="Back to library" onClick={home}>
                <ArrowLeft size={20} />
              </button>
              <div>
                <h1>{project.title}</h1>
                <p>
                  {time(project.duration)} duration <span>·</span> {project.width} × {project.height} source resolution
                  {project.is_link && (
                    <>
                      <span>·</span>
                      <span className="badge-link">
                        <Link2 size={11} /> Online Link
                      </span>
                    </>
                  )}
                </p>
              </div>
              <div className="studio-heading-actions">
                <button className="button" onClick={() => setSuggestOpen(true)} disabled={working}>
                  <Sparkles size={16} /> Research & Find Clips
                </button>
                <button
                  className="button primary"
                  disabled={working || !clip}
                  onClick={() =>
                    act('Starting export', async () => {
                      await saveClip();
                      const next = await api<Job>(`/projects/${project.id}/clips/${clip!.id}/export`, {
                        method: 'POST',
                        body: JSON.stringify({ resolution })
                      });
                      setJob(next);
                      setTab('exports');
                    })
                  }
                >
                  <Download size={16} /> Export Clip MP4
                </button>
              </div>
            </div>

            {project.analysis && <AnalysisPanel analysis={project.analysis} />}

            <div className="studio-grid">
              {/* Studio Left Panel */}
              <section className="clip-panel">
                <div className="panel-tabs">
                  {(['clips', 'transcript', 'exports'] as const).map((t) => (
                    <button className={tab === t ? 'active' : ''} onClick={() => setTab(t)} key={t}>
                      {t === 'clips' ? 'Clips' : t === 'transcript' ? 'Transcript' : 'Exports'}
                      <span>{t === 'clips' ? project.clips.length : t === 'transcript' ? segments.length : exported.length}</span>
                    </button>
                  ))}
                </div>

                {tab === 'clips' && (
                  <>
                    <div className="panel-top">
                      <span className="muted">YOUR SHORT CLIPS</span>
                      <button className="icon-button" aria-label="Add clip" disabled={working} onClick={newClip}>
                        <Plus size={18} />
                      </button>
                    </div>
                    <div className="clip-list">
                      {project.clips.length ? (
                        project.clips.map((c, i) => (
                          <button className={`clip-list-item ${clip?.id === c.id ? 'selected' : ''}`} key={c.id} onClick={() => selectClip(c)}>
                            <span className="clip-number">{String(i + 1).padStart(2, '0')}</span>
                            <span>
                              <strong>{c.title}</strong>
                              <small>
                                {time(c.start)} — {time(c.end)} <b>{Math.round(c.end - c.start)}s</b>
                              </small>
                              {c.reason && <em>{c.reason}</em>}
                            </span>
                            <ChevronRight size={16} />
                          </button>
                        ))
                      ) : (
                        <div className="panel-empty">
                          <Scissors size={32} />
                          <h3>No clips created yet</h3>
                          <p>Trim a clip by hand or use AI analysis to automatically find the best moments.</p>
                          <button className="button primary small" disabled={working} onClick={newClip}>
                            <Plus size={15} /> Create a clip
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {tab === 'transcript' && (
                  <>
                    <div className="transcript-actions">
                      <button className="button primary small" onClick={() => setTranscribeOpen(true)} disabled={working}>
                        <Captions size={15} /> Transcribe (GPU)
                      </button>
                      <button className="button small" onClick={() => transcriptInput.current?.click()} disabled={working}>
                        <Upload size={15} /> Import SRT
                      </button>
                      <input
                        ref={transcriptInput}
                        hidden
                        type="file"
                        accept=".srt,.vtt"
                        onChange={(e) => {
                          if (e.target.files?.[0]) addTranscript(e.target.files[0]);
                          e.target.value = '';
                        }}
                      />
                    </div>
                    <div className="transcript-list">
                      {!segments.length && (
                        <div className="panel-empty">
                          <Captions size={30} />
                          <h3>Generate speech captions</h3>
                          <p>Transcribe fast with your laptop GPU (RTX 4050) & 8 CPU threads, or import an SRT/VTT file.</p>
                        </div>
                      )}
                      {segments.map((s, i) => (
                        <div className={`segment ${currentTime >= s.start && currentTime < s.end ? 'current' : ''}`} key={s.id || i}>
                          <div>
                            <button
                              className="seek-button"
                              onClick={() => {
                                if (video.current) video.current.currentTime = s.start;
                              }}
                            >
                              {time(s.start)}
                            </button>
                            <input
                              aria-label={`Caption ${i + 1} start`}
                              type="number"
                              min="0"
                              step="0.1"
                              value={s.start}
                              onChange={(e) => {
                                setSegments(segments.map((x, k) => (k === i ? { ...x, start: Number(e.target.value) } : x)));
                                setDirtyTranscript(true);
                              }}
                            />
                            <span>→</span>
                            <input
                              aria-label={`Caption ${i + 1} end`}
                              type="number"
                              min="0"
                              step="0.1"
                              value={s.end}
                              onChange={(e) => {
                                setSegments(segments.map((x, k) => (k === i ? { ...x, end: Number(e.target.value) } : x)));
                                setDirtyTranscript(true);
                              }}
                            />
                            <button
                              aria-label={`Delete caption ${i + 1}`}
                              className="icon-button"
                              onClick={() => {
                                setSegments(segments.filter((_, k) => k !== i));
                                setDirtyTranscript(true);
                              }}
                            >
                              <X size={14} />
                            </button>
                          </div>
                          <textarea
                            aria-label={`Caption ${i + 1} text`}
                            value={s.text}
                            rows={2}
                            onChange={(e) => {
                              setSegments(segments.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)));
                              setDirtyTranscript(true);
                            }}
                          />
                        </div>
                      ))}
                    </div>
                    <div className="transcript-footer">
                      <button
                        className="button small"
                        onClick={() => {
                          const start = Math.min(currentTime, Math.max(0, project.duration - 0.1));
                          setSegments([...segments, { id: crypto.randomUUID(), start, end: Math.min(project.duration, start + 3), text: '' }]);
                          setDirtyTranscript(true);
                        }}
                      >
                        <Plus size={14} /> Add caption
                      </button>
                      <button className="button primary small" disabled={working || !dirtyTranscript} onClick={saveTranscript}>
                        Save edits
                      </button>
                      {project.segments.length > 0 && (
                        <a className="icon-button" title="Download SRT file" href={`${API}/projects/${project.id}/transcript?format=srt`} download>
                          <Download size={16} />
                        </a>
                      )}
                    </div>
                  </>
                )}

                {tab === 'exports' && (
                  <div className="panel-exports">
                    {exported.length ? (
                      exported.map((e) => <ExportCard key={e.id} item={e} />)
                    ) : (
                      <div className="panel-empty">
                        <Download size={30} />
                        <h3>Ready to export</h3>
                        <p>Adjust framing, choose caption styles, and render your finished MP4.</p>
                      </div>
                    )}
                  </div>
                )}
              </section>

              {/* Studio Center Panel: Video Preview with Interactive Crop Drag & Grid */}
              <section className="preview-panel">
                <div className="preview-heading">
                  <span>
                    <Monitor size={16} /> VIDEO PREVIEW
                  </span>
                  <div className="preview-toolbar">
                    <button
                      className={`button small ${showCropGrid ? 'primary' : ''}`}
                      onClick={() => setShowCropGrid(!showCropGrid)}
                      title="Toggle Rule of Thirds Crop Grid Guide"
                    >
                      <Grid size={14} /> {showCropGrid ? 'Crop Grid On' : 'Crop Grid'}
                    </button>
                    <span className="tiny-tag">{clip?.aspect || 'SOURCE'}</span>
                  </div>
                </div>

                <div className="video-stage">
                  <div
                    ref={frame}
                    onPointerDown={(e) => {
                      if (clip?.fit !== 'crop') return;
                      cropDrag.current = { x: e.clientX, y: e.clientY, cropX: clip.crop_x, cropY: clip.crop_y ?? 0.5 };
                      e.currentTarget.setPointerCapture(e.pointerId);
                    }}
                    onPointerMove={(e) => {
                      const d = cropDrag.current;
                      if (!d || !clip) return;
                      const dx = sourceWidth - frameSize.width;
                      const dy = sourceHeight - frameSize.height;
                      setClip({
                        ...clip,
                        crop_x: dx > 0.1 ? Math.max(0, Math.min(1, d.cropX - (e.clientX - d.x) / dx)) : clip.crop_x,
                        crop_y: dy > 0.1 ? Math.max(0, Math.min(1, d.cropY - (e.clientY - d.y) / dy)) : clip.crop_y ?? 0.5
                      });
                      setDirtyClip(true);
                    }}
                    onPointerUp={() => {
                      cropDrag.current = null;
                    }}
                    onPointerCancel={() => {
                      cropDrag.current = null;
                    }}
                    className={`video-frame ${clip?.fit === 'contain' ? 'contain' : ''}`}
                    style={{ aspectRatio: clip?.aspect.replace(':', ' / ') || `${project.width} / ${project.height}` }}
                  >
                    <video
                      ref={video}
                      src={project.video_url}
                      playsInline
                      preload="metadata"
                      onPause={() => setIsPlaying(false)}
                      onTimeUpdate={(e) => {
                        const v = e.currentTarget;
                        setCurrentTime(v.currentTime);
                        if (clip && !v.paused && v.currentTime >= clip.end) {
                          v.pause();
                          v.currentTime = clip.end;
                        }
                      }}
                      onPlay={(e) => {
                        setIsPlaying(true);
                        if (clip && (e.currentTarget.currentTime < clip.start || e.currentTarget.currentTime >= clip.end)) {
                          e.currentTarget.currentTime = clip.start;
                        }
                      }}
                      style={videoStyle}
                    />

                    {/* Interactive Rule of Thirds Crop Grid Guide */}
                    {showCropGrid && clip?.fit === 'crop' && (
                      <div className="crop-grid-overlay">
                        <div />
                        <div />
                        <div />
                        <div />
                        <div />
                        <div />
                        <div />
                        <div />
                        <div />
                      </div>
                    )}

                    {clip?.burn_captions && clip.caption_style !== 'none' && currentCaption && (
                      <div
                        className={`preview-caption ${clip.caption_style}`}
                        style={
                          {
                            color: clip.caption_color,
                            fontSize: `${Math.max(16, Math.min(26, Math.round((clip.font_size * frameSize.width) / 720)))}px`,
                            '--accent': clip.accent_color
                          } as React.CSSProperties
                        }
                      >
                        <span className="preview-caption-bubble">{currentCaption}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="playback-controls">
                  <button
                    className="button small"
                    aria-label={isPlaying ? 'Pause' : 'Play'}
                    onClick={() => {
                      if (video.current) {
                        if (video.current.paused) video.current.play().catch((e) => setError(e.message));
                        else video.current.pause();
                      }
                    }}
                  >
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />} {isPlaying ? 'Pause' : 'Play'}
                  </button>
                  <span>
                    {time(currentTime)} / {time(project.duration)}
                  </span>
                </div>

                <div className="preview-note">
                  {clip?.fit === 'crop' ? 'Click & drag the video frame to pan the crop. Exact framing matches your exported MP4.' : 'Contain mode adds clean black pillarboxes.'}
                </div>

                {/* Timeline Window */}
                <div className="timeline">
                  <div>
                    <span className="mono">{time(currentTime)}</span>
                    <span className="muted">{time(project.duration)}</span>
                  </div>
                  <div className="timeline-track">
                    <div className="timeline-wave">
                      {Array.from({ length: 70 }, (_, i) => (
                        <span key={i} style={{ height: `${i % 5 === 0 ? 24 : 11}px` }} />
                      ))}
                    </div>
                    {clip && (
                      <div
                        className="trim-window"
                        style={{
                          left: `${(clip.start / project.duration) * 100}%`,
                          width: `${((clip.end - clip.start) / project.duration) * 100}%`
                        }}
                      />
                    )}
                    <input
                      aria-label="Video playhead"
                      type="range"
                      min="0"
                      max={project.duration}
                      step="0.05"
                      value={currentTime}
                      onChange={(e) => {
                        const t = Number(e.target.value);
                        if (video.current) video.current.currentTime = t;
                        setCurrentTime(t);
                      }}
                    />
                  </div>
                  <div className="timeline-labels">
                    <span>0:00</span>
                    <span>{time(project.duration / 2)}</span>
                    <span>{time(project.duration)}</span>
                  </div>
                </div>

                {clip && (
                  <div className="trim-controls">
                    <label>
                      START{' '}
                      <input
                        type="number"
                        aria-label="Clip start in seconds"
                        min="0"
                        max={project.duration}
                        step="0.1"
                        value={clip.start}
                        onChange={(e) => updateClip('start', Number(e.target.value))}
                      />
                    </label>
                    <span>
                      <Scissors size={16} /> {(clip.end - clip.start).toFixed(1)}s
                    </span>
                    <label>
                      END{' '}
                      <input
                        type="number"
                        aria-label="Clip end in seconds"
                        min="0"
                        max={project.duration}
                        step="0.1"
                        value={clip.end}
                        onChange={(e) => updateClip('end', Number(e.target.value))}
                      />
                    </label>
                  </div>
                )}
              </section>

              {/* Studio Right Panel: Video Crop, Format & Caption Settings */}
              <section className="inspector">
                <div className="panel-title">
                  <Layers size={18} />
                  <h2>Crop & Clip Settings</h2>
                  {dirtyClip && <span className="unsaved-dot" title="Unsaved changes" />}
                </div>

                {clip ? (
                  <>
                    <div className="inspector-content">
                      <label className="field">
                        Clip title
                        <input value={clip.title} maxLength={140} onChange={(e) => updateClip('title', e.target.value)} />
                      </label>

                      {/* Video Aspect Ratio & Cropping Section */}
                      <fieldset>
                        <legend>Aspect Ratio & Format</legend>
                        <div className="format-options">
                          {(
                            [
                              { id: '9:16', label: '9:16', desc: 'Shorts/Reels', iconClass: 'a916' },
                              { id: '1:1', label: '1:1', desc: 'Square', iconClass: 'a11' },
                              { id: '4:5', label: '4:5', desc: 'Feed', iconClass: 'a45' },
                              { id: '16:9', label: '16:9', desc: 'Landscape', iconClass: 'a169' }
                            ] as const
                          ).map((item) => (
                            <button
                              className={clip.aspect === item.id ? 'selected' : ''}
                              onClick={() => updateClip('aspect', item.id)}
                              key={item.id}
                            >
                              <span className={`format-icon ${item.iconClass}`} />
                              <strong>{item.label}</strong>
                              <small>{item.desc}</small>
                            </button>
                          ))}
                        </div>
                      </fieldset>

                      <label className="field">
                        Framing Mode
                        <select value={clip.fit} onChange={(e) => updateClip('fit', e.target.value as Clip['fit'])}>
                          <option value="crop">Fill & Crop Edges (Full Screen)</option>
                          <option value="contain">Fit Full Video (Black Bars)</option>
                        </select>
                      </label>

                      {/* Dedicated Crop Video Controls */}
                      {clip.fit === 'crop' && (
                        <div className="crop-controls">
                          <div className="crop-heading">
                            <strong>Crop Framing Controls</strong>
                            <button
                              className="button small"
                              onClick={() => {
                                setClip({ ...clip, crop_x: 0.5, crop_y: 0.5, zoom: 1 });
                                setDirtyClip(true);
                              }}
                            >
                              <RotateCcw size={13} /> Reset
                            </button>
                          </div>

                          <div className="crop-presets">
                            <button
                              className="button small"
                              onClick={() => {
                                setClip({ ...clip, crop_x: 0.5, crop_y: 0.5 });
                                setDirtyClip(true);
                              }}
                            >
                              Center
                            </button>
                            <button
                              className="button small"
                              onClick={() => {
                                setClip({ ...clip, crop_x: 0.25, crop_y: 0.5 });
                                setDirtyClip(true);
                              }}
                            >
                              Left
                            </button>
                            <button
                              className="button small"
                              onClick={() => {
                                setClip({ ...clip, crop_x: 0.75, crop_y: 0.5 });
                                setDirtyClip(true);
                              }}
                            >
                              Right
                            </button>
                            <button
                              className="button small"
                              onClick={() => {
                                setClip({ ...clip, crop_x: 0.5, crop_y: 0.2 });
                                setDirtyClip(true);
                              }}
                            >
                              Top
                            </button>
                          </div>

                          <label className="field">
                            Horizontal Pan ({Math.round(clip.crop_x * 100)}%)
                            <span className="range-labels">
                              <span>Left</span>
                              <span>Right</span>
                            </span>
                            <input
                              aria-label="Horizontal crop position"
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={clip.crop_x}
                              onChange={(e) => updateClip('crop_x', Number(e.target.value))}
                            />
                          </label>

                          <label className="field">
                            Vertical Pan ({Math.round((clip.crop_y ?? 0.5) * 100)}%)
                            <span className="range-labels">
                              <span>Top</span>
                              <span>Bottom</span>
                            </span>
                            <input
                              aria-label="Vertical crop position"
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={clip.crop_y ?? 0.5}
                              onChange={(e) => updateClip('crop_y', Number(e.target.value))}
                            />
                          </label>

                          <label className="field">
                            Zoom Multiplier ({(clip.zoom ?? 1).toFixed(2)}×)
                            <input
                              aria-label="Crop zoom"
                              type="range"
                              min="1"
                              max="3"
                              step="0.05"
                              value={clip.zoom ?? 1}
                              onChange={(e) => updateClip('zoom', Number(e.target.value))}
                            />
                          </label>

                          <p className="hint">Tip: You can also drag the video preview directly to adjust framing.</p>
                        </div>
                      )}

                      <div className="inspector-divider" />

                      {/* Captions Controls */}
                      <div className="toggle-row">
                        <span>
                          <Captions size={17} /> Burn-in Captions
                        </span>
                        <button
                          className={`toggle ${clip.burn_captions ? 'on' : ''}`}
                          role="switch"
                          aria-label="Burn-in captions"
                          aria-checked={clip.burn_captions}
                          onClick={() => updateClip('burn_captions', !clip.burn_captions)}
                        >
                          <span />
                        </button>
                      </div>

                      {clip.burn_captions && (
                        <>
                          <label className="field">
                            Caption Style
                            <select value={clip.caption_style} onChange={(e) => updateClip('caption_style', e.target.value as Clip['caption_style'])}>
                              <option value="bold">Bold · High Contrast Outline</option>
                              <option value="clean">Clean · Subtitle Box</option>
                              <option value="karaoke">Karaoke · Animated Word Highlight</option>
                              <option value="none">None</option>
                            </select>
                          </label>
                          <div className="field-row">
                            <label className="field">
                              Font Size
                              <input
                                type="number"
                                min="16"
                                max="96"
                                value={clip.font_size}
                                onChange={(e) => updateClip('font_size', Number(e.target.value))}
                              />
                            </label>
                            <label className="field">
                              Text Color
                              <input
                                aria-label="Caption text color"
                                type="color"
                                value={clip.caption_color}
                                onChange={(e) => updateClip('caption_color', e.target.value)}
                              />
                            </label>
                            <label className="field">
                              Highlight Color
                              <input
                                aria-label="Caption highlight color"
                                type="color"
                                value={clip.accent_color}
                                onChange={(e) => updateClip('accent_color', e.target.value)}
                              />
                            </label>
                          </div>
                          {!segments.length && <p className="hint warning">Transcribe or add captions to include them in the rendered video.</p>}
                        </>
                      )}

                      <div className="inspector-divider" />

                      <label className="field">
                        Export Resolution
                        <select value={resolution} onChange={(e) => setResolution(Number(e.target.value))}>
                          <option value={720}>720p HD · Ultra Fast Render</option>
                          <option value={1080}>1080p Full HD · Highest Quality</option>
                        </select>
                      </label>
                    </div>

                    <div className="inspector-footer">
                      <button
                        className="button primary"
                        disabled={working || !dirtyClip}
                        onClick={() =>
                          act('Saving clip', async () => {
                            await saveClip();
                            setNotice('Clip settings saved');
                          })
                        }
                      >
                        <Check size={16} />
                        {dirtyClip ? 'Save changes' : 'Saved'}
                      </button>
                      <button
                        className="icon-button danger-on-hover"
                        aria-label="Delete clip"
                        disabled={working}
                        onClick={() => {
                          if (confirm(`Delete “${clip.title}”?`)) {
                            act('Deleting clip', async () => {
                              await api(`/projects/${project.id}/clips/${clip.id}`, { method: 'DELETE' });
                              await refreshProject(project.id, false);
                            });
                          }
                        }}
                      >
                        <Trash2 size={17} />
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="panel-empty">
                    <Layers size={32} />
                    <h3>Select a clip</h3>
                    <p>Choose or create a clip to crop, adjust framing, and customize subtitle styles.</p>
                    <button className="button primary small" onClick={newClip} disabled={working}>
                      <Plus size={15} /> Create clip
                    </button>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        <footer className="app-footer">
          <span>CLIPFORGE STUDIO</span>
          <span>Fast Local Video Repurposing</span>
          <span>
            <HardDrive size={13} /> {health?.gpu_name || 'NVIDIA GPU Acceleration'}
          </span>
        </footer>
      </main>

      {/* Upload & Link Modal with Live Dynamic Percentage */}
      {uploadOpen &&
        modal(
          'Add Video to ClipForge',
          <>
            <div className="modal-tabs">
              <button
                type="button"
                className={`modal-tab ${uploadModalTab === 'file' ? 'active' : ''}`}
                onClick={() => setUploadModalTab('file')}
              >
                <Upload size={16} /> Upload Video File
              </button>
              <button
                type="button"
                className={`modal-tab ${uploadModalTab === 'link' ? 'active' : ''}`}
                onClick={() => setUploadModalTab('link')}
              >
                <Link2 size={16} /> Import Link (YouTube, Instagram, Facebook)
              </button>
            </div>

            {uploadModalTab === 'file' ? (
              <>
                <p className="modal-intro">Choose a video from your computer. Video processing and speech transcription stay 100% local.</p>
                <button
                  className={`upload-zone ${uploadFile ? 'chosen' : ''}`}
                  onClick={() => fileInput.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    setUploadFile(e.dataTransfer.files[0] || null);
                  }}
                >
                  <span className="upload-icon">{uploadFile ? <Film size={30} /> : <Upload size={30} />}</span>
                  <strong>{uploadFile ? uploadFile.name : 'Choose a video file or drag and drop'}</strong>
                  <span>{uploadFile ? bytes(uploadFile.size) : 'MP4, MOV, WebM, MKV, AVI · Up to 2 GB'}</span>
                  <small>{uploadFile ? 'Click to select a different video' : 'Your video stays strictly on your computer'}</small>
                </button>
                <input ref={fileInput} type="file" hidden accept="video/*,.mkv" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />

                {uploadStatus}

                <label className="field">
                  Project Title <span className="muted">(Optional)</span>
                  <input placeholder="e.g. Podcast Highlights - Episode 12" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} maxLength={160} />
                </label>

                <div className="modal-footer">
                  <span className="hint">
                    <ShieldCheck size={15} /> Zero external cloud uploads
                  </span>
                  <button className="button primary" disabled={!uploadFile || working} onClick={upload}>
                    {uploadProgress ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}
                    {uploadProgress ? (uploadProgress.stage === 'uploading' ? `Uploading (${uploadPct}%)…` : 'Processing…') : 'Import Video'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="modal-intro">Paste a YouTube, Instagram Reel, or Facebook video link. ClipForge extracts captions and a crisp preview without downloading massive master files.</p>

                <label className="field">
                  Video URL <span className="required">*</span>
                  <input
                    type="url"
                    placeholder="https://youtube.com/..., https://instagram.com/reel/..., or https://facebook.com/..."
                    value={linkUrl}
                    onChange={(e) => setLinkUrl(e.target.value)}
                    autoFocus
                  />
                </label>

                <label className="field">
                  Project Title <span className="muted">(Optional - auto-detected from video)</span>
                  <input
                    placeholder="Leave empty to use online video title"
                    value={linkTitle}
                    onChange={(e) => setLinkTitle(e.target.value)}
                    maxLength={160}
                  />
                </label>

                <label className="field">
                  Browser Cookies <span className="muted">(Optional - for login-gated Instagram or Facebook reels)</span>
                  <select value={linkCookies} onChange={(e) => setLinkCookies(e.target.value as any)}>
                    <option value="none">None (Direct public download)</option>
                    <option value="chrome">Chrome (Use active Chrome cookies for login/private content)</option>
                    <option value="edge">Edge (Use active Edge cookies for login/private content)</option>
                  </select>
                </label>

                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={linkFetchSubs}
                    onChange={(e) => setLinkFetchSubs(e.target.checked)}
                  />
                  <span>
                    Auto-import video subtitles & captions
                    <small>Extracts existing subtitles in seconds so you can research & find clips right away</small>
                  </span>
                </label>

                <div className="link-info-box">
                  <Sparkles size={18} />
                  <div>
                    <strong>Full-Quality Slices on Demand</strong>
                    <span>ClipForge fetches metadata, instant captions, and a crisp 720p preview. High definition (up to 1080p) is fetched for the exact clip slices you choose!</span>
                  </div>
                </div>

                <div className="modal-footer">
                  <span className="hint">
                    <HardDrive size={15} /> Slices downloaded on demand
                  </span>
                  <button className="button primary" disabled={!linkUrl.trim() || working} onClick={importLink}>
                    <ArrowRight size={17} /> Import from Link
                  </button>
                </div>
              </>
            )}
          </>,
          () => setUploadOpen(false)
        )}

      {/* AI Research & Find Best Clips Modal */}
      {suggestOpen &&
        modal(
          'Deep Research & Find Best Clips',
          <>
            <p className="modal-intro">
              Ollama reads your complete transcript, generates a comprehensive video summary, and performs research to identify the most viral, coherent clip
              candidates.
            </p>

            <label className="field">
              Analysis Method
              <select value={provider} onChange={(e) => setProvider(e.target.value as typeof provider)}>
                <option value="ollama">Ollama · Local LLM Deep Research</option>
                <option value="heuristic">Transcript Heuristic · Fast, Rule-Based (No AI)</option>
              </select>
            </label>

            {provider === 'ollama' && (
              <label className="field">
                Ollama Model
                <select value={model} onChange={(e) => setModel(e.target.value)}>
                  {Array.from(new Set([model, 'qwen3.5:9b', ...(health?.models || [])])).map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
                <small className="hint">
                  Default: <strong>qwen3.5:9b</strong>. Powered by your local Ollama server.
                </small>
              </label>
            )}

            <div className="field-row">
              <label className="field">
                Min Seconds
                <input type="number" min="5" max="300" value={minDuration} onChange={(e) => setMinDuration(Number(e.target.value))} />
              </label>
              <label className="field">
                Max Seconds
                <input type="number" min="5" max="300" value={maxDuration} onChange={(e) => setMaxDuration(Number(e.target.value))} />
              </label>
              <label className="field">
                Number of Clips
                <input type="number" min="1" max="10" value={count} onChange={(e) => setCount(Number(e.target.value))} />
              </label>
            </div>

            {provider === 'ollama' && (
              <label className="checkbox-field">
                <input type="checkbox" checked={useWebSearch} disabled={!health?.tavily_configured} onChange={(e) => setUseWebSearch(e.target.checked)} />
                <span>
                  Enable Web Research with Tavily API
                  <small>
                    {health?.tavily_configured
                      ? 'Tavily search enabled! Researches trending angles and viral topic context.'
                      : 'Attach your TAVILY_API_KEY in the .env file to enable web search trends.'}
                  </small>
                </span>
              </label>
            )}

            {!project?.segments.length && <p className="hint warning">Transcribe your video first so the AI can analyze the complete speech transcript.</p>}
            {dirtyTranscript && <p className="hint warning">Save your transcript edits before running clip analysis.</p>}

            <div className="modal-footer">
              <button className="button" onClick={() => setSuggestOpen(false)}>
                Cancel
              </button>
              <button
                className="button primary"
                disabled={working || !project?.segments.length || dirtyTranscript}
                onClick={() =>
                  act('Finding best clips', async () => {
                    if (!project) return;
                    if (minDuration <= 0 || maxDuration < minDuration || count < 1 || count > 10)
                      throw new Error('Check your clip duration and count settings.');
                    setJob(
                      await api<Job>(`/projects/${project.id}/suggest`, {
                        method: 'POST',
                        body: JSON.stringify({
                          provider,
                          model,
                          min_duration: minDuration,
                          max_duration: maxDuration,
                          count,
                          use_web_search: provider === 'ollama' && useWebSearch
                        })
                      })
                    );
                    setSuggestOpen(false);
                    setTab('clips');
                  })
                }
              >
                <Sparkles size={16} /> Research & Find Best Clips
              </button>
            </div>
          </>,
          () => setSuggestOpen(false)
        )}

      {/* Transcribe Modal with GPU + 8 CPU Worker acceleration */}
      {transcribeOpen &&
        modal(
          'Transcribe Audio with Whisper',
          <>
            <p className="modal-intro">
              High-speed speech recognition using faster-whisper. Accelerated with your laptop NVIDIA GPU (CUDA float16) and 8 CPU threads.
            </p>

            <label className="field">
              Whisper Speech Model
              <select value={whisperModel} onChange={(e) => setWhisperModel(e.target.value)}>
                <option value="base.en">Base English (Cached & Blazing Fast on GPU)</option>
                <option value="tiny">Tiny · Fastest, basic accuracy</option>
                <option value="base">Base · Multilingual fast</option>
                <option value="small">Small · Balanced high accuracy</option>
                <option value="medium">Medium · Professional studio quality</option>
              </select>
            </label>

            <div className="field-row">
              <label className="field">
                Acceleration Hardware
                <select value={device} onChange={(e) => setDevice(e.target.value as typeof device)}>
                  <option value="auto">Auto · Prefer NVIDIA GPU (Fastest)</option>
                  <option value="cuda" disabled={!health?.transcription_gpu_available}>
                    NVIDIA GPU (CUDA)
                  </option>
                  <option value="cpu">CPU Only</option>
                </select>
              </label>

              <label className="field">
                CPU Threads
                <input type="number" min="1" max="32" value={cpuThreads} onChange={(e) => setCpuThreads(Number(e.target.value))} />
              </label>
            </div>

            <p className="hint">
              {health?.transcription_gpu_available ? (
                <span style={{ color: '#4b742e', fontWeight: 700 }}>
                  ✓ {health.gpu_name || 'NVIDIA RTX 4050 Laptop GPU'} detected! Using GPU float16 + 8 CPU threads for maximum speed.
                </span>
              ) : (
                'GPU runtime not found; using multi-threaded CPU mode.'
              )}
            </p>

            <label className="field">
              Audio Language
              <input value={language} placeholder="Auto-detect (or en, es, hi, fr…)" maxLength={12} onChange={(e) => setLanguage(e.target.value)} />
            </label>

            <label className="checkbox-field">
              <input type="checkbox" checked={allowDownload} onChange={(e) => setAllowDownload(e.target.checked)} />
              <span>
                Allow downloading speech weights if missing
                <small>base.en is already cached on your computer and requires no download.</small>
              </span>
            </label>

            <div className="modal-footer">
              <button className="button" onClick={() => setTranscribeOpen(false)}>
                Cancel
              </button>
              <button
                className="button primary"
                disabled={working || !health?.transcription_available}
                onClick={() =>
                  act('Starting transcription', async () => {
                    if (!project) return;
                    setJob(
                      await api<Job>(`/projects/${project.id}/transcribe`, {
                        method: 'POST',
                        body: JSON.stringify({
                          model: whisperModel,
                          language: language.trim() || undefined,
                          allow_download: allowDownload,
                          device,
                          cpu_threads: cpuThreads
                        })
                      })
                    );
                    setTranscribeOpen(false);
                  })
                }
              >
                <Captions size={16} /> Start GPU Transcription
              </button>
            </div>
          </>,
          () => setTranscribeOpen(false)
        )}

      {/* Settings / Hardware Modal */}
      {settingsOpen &&
        modal(
          'Hardware & Toolkit Status',
          <>
            <p className="modal-intro">ClipForge runs 100% locally on your laptop without requiring cloud AI subscriptions.</p>
            <div className="status-list">
              <Status
                label="Laptop GPU Acceleration"
                detail={health?.gpu_name ? `${health.gpu_name} · CUDA Float16 Active` : 'CPU Mode'}
                ok={Boolean(health?.transcription_gpu_available)}
              />
              <Status label="Video Processing Engine" detail="FFmpeg + FFprobe on PATH" ok={Boolean(health?.ffmpeg && health?.ffprobe)} />
              <Status
                label="Ollama Local LLM"
                detail={health?.ollama ? `Connected · Default: ${health.default_model || 'qwen3.5:9b'}` : 'Start Ollama to enable Qwen3.5 9B'}
                ok={Boolean(health?.ollama)}
              />
              <Status
                label="Whisper Speech Engine"
                detail={health?.transcription_available ? 'faster-whisper installed & ready' : 'Not installed'}
                ok={Boolean(health?.transcription_available)}
              />
              <Status
                label="Tavily Web Research"
                detail={health?.tavily_configured ? 'TAVILY_API_KEY configured in .env' : 'Attach TAVILY_API_KEY in .env to enable web search'}
                ok={Boolean(health?.tavily_configured)}
              />
            </div>

            <div className="info-box">
              <Cpu size={20} />
              <div>
                <strong>NVIDIA GeForce RTX 4050 Laptop GPU + 8 CPU Workers</strong>
                <p>Whisper transcription uses CUDA float16 batching with 8 worker threads for maximum throughput.</p>
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="button"
                disabled={working}
                onClick={() =>
                  act('Refreshing hardware', async () => {
                    setHealth(await api<Health>('/health'));
                    setNotice('Hardware status refreshed');
                  })
                }
              >
                Refresh Status
              </button>
              <button className="button primary" onClick={() => setSettingsOpen(false)}>
                Back to Studio <ArrowRight size={16} />
              </button>
            </div>
          </>,
          () => setSettingsOpen(false)
        )}

      {busy && !job && (
        <div className="busy-toast" role="status">
          <LoaderCircle size={17} className="spin" />
          {busy}…
        </div>
      )}
    </div>
  );
}

function ExportCard({ item, subtitle }: { item: Export; subtitle?: string }) {
  return (
    <article className="export-card">
      {item.preview_url ? (
        <video aria-label={`Finished export: ${item.title}`} src={item.preview_url} poster={item.thumbnail_url} controls playsInline preload="none" />
      ) : item.thumbnail_url ? (
        <img src={item.thumbnail_url} alt="Export thumbnail" />
      ) : (
        <div className="export-placeholder">
          <Clapperboard size={30} />
        </div>
      )}
      <div>
        <h3>{item.title}</h3>
        {subtitle && <p>{subtitle}</p>}
        <small>
          <CheckCircle2 size={13} /> MP4 Video <span>·</span> {bytes(item.size)}
        </small>
        <div className="export-links">
          <a className="button primary small" href={item.url} download>
            <Download size={14} /> Download MP4
          </a>
          {item.thumbnail_url && (
            <a href={item.thumbnail_url} download className="icon-button" aria-label={`Download thumbnail for ${item.title}`} title="Download thumbnail">
              <Film size={16} />
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

function Status({ label, detail, ok }: { label: string; detail: string; ok: boolean }) {
  return (
    <div className="status-row">
      <span className={`status-icon ${ok ? 'good' : ''}`}>{ok ? <Check size={17} /> : <MoreHorizontal size={17} />}</span>
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
      <span className={`tiny-tag ${ok ? 'good' : ''}`}>{ok ? 'READY' : 'OPTIONAL'}</span>
    </div>
  );
}

function AnalysisPanel({ analysis }: { analysis: Analysis }) {
  const [open, setOpen] = useState(true);
  const coverage =
    typeof analysis.coverage === 'string'
      ? analysis.coverage
      : analysis.coverage
      ? Object.entries(analysis.coverage)
          .filter(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
          .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`)
          .join(' · ')
      : '';

  return (
    <section className="analysis-panel">
      <button className="analysis-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>
          <Sparkles size={18} />
          <strong>Full-Transcript Video Summary & AI Insights</strong>
        </span>
        <span>
          {open ? 'Hide Summary' : 'Show Summary'} <ChevronRight size={16} className={open ? 'rotate' : ''} />
        </span>
      </button>
      {open && (
        <div className="analysis-content">
          <p>{analysis.summary}</p>
          {analysis.topics?.length ? (
            <div className="topic-tags">
              {analysis.topics.map((topic, i) => (
                <span key={`${topic}-${i}`}>{topic}</span>
              ))}
            </div>
          ) : null}
          {coverage && <p className="coverage-note">{coverage}</p>}
          {analysis.warnings?.map((warning, i) => (
            <p className="hint warning" key={i}>
              {warning}
            </p>
          ))}
          {analysis.web_sources?.length ? (
            <div className="web-sources">
              <strong>Web Research Sources (Tavily)</strong>
              {analysis.web_sources.map((source, i) => (
                <a key={i} href={/^https?:\/\//i.test(source.url) ? source.url : undefined} target="_blank" rel="noopener noreferrer">
                  {source.title || source.url}
                </a>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
