from pathlib import Path
p=Path(r'E:\REA\clipforge\frontend\src\App.tsx')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('useRef, useState','useRef, useState, type CSSProperties')
s=s.replace('Scissors, Settings2','Scissors, Play, Pause, RotateCcw, Settings2')
s=s.replace('Project, Segment','Project, Segment, Analysis')
s=s.replace("crop_x: .5, caption_style", "crop_x: .5, crop_y: .5, zoom: 1, caption_style")
s=s.replace("accent_color: '#baff39'", "accent_color: '#edc49c'")
s=s.replace('crop_x: clip.crop_x, caption_style','crop_x: clip.crop_x, crop_y: clip.crop_y ?? .5, zoom: clip.zoom ?? 1, caption_style')
s=s.replace("useState<'heuristic'|'ollama'>('heuristic')","useState<'heuristic'|'ollama'>('ollama')")
s=s.replace("useState('qwen2.5:7b')", "useState('qwen3.5:9b')")
s=s.replace("const [allowDownload, setAllowDownload] = useState(false);", """const [allowDownload, setAllowDownload] = useState(false);
  const [device, setDevice] = useState<'auto'|'cuda'|'cpu'>('auto');
  const [cpuThreads, setCpuThreads] = useState(8);
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{loaded:number;total:number;stage:'uploading'|'preparing'}|null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const frame = useRef<HTMLDivElement>(null);
  const [frameSize, setFrameSize] = useState({width:360,height:640});
  const cropDrag = useRef<{x:number;y:number;cropX:number;cropY:number}|null>(null);""")
s=s.replace("setProject(p);\n", "setProject(p);\n      if (p.active_job && ['queued','running'].includes(p.active_job.status)) setJob(p.active_job);\n",1)
s=s.replace("setHealth(h); if(h.transcription_cached_models", "setHealth(h); if(h.default_model) setModel(h.default_model); if(h.transcription_cpu_threads) setCpuThreads(h.transcription_cpu_threads); if(h.transcription_cached_models")
s=s.replace("  const working = Boolean(busy)", """  useEffect(() => {
    if (!job || !['queued','running'].includes(job.status)) { localStorage.removeItem('clipforge-active-job'); return; }
    localStorage.setItem('clipforge-active-job', JSON.stringify({id:job.id,project_id:job.project_id || activeProject.current}));
    const interval = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [job?.id,job?.status]);
  useEffect(() => {
    try { const saved=JSON.parse(localStorage.getItem('clipforge-active-job')||'null'); if(saved?.id) api<Job>(`/jobs/${saved.id}`).then(setJob).catch(()=>localStorage.removeItem('clipforge-active-job')); } catch { localStorage.removeItem('clipforge-active-job'); }
  }, []);
  useEffect(() => {
    const element=frame.current; if(!element) return;
    const observer=new ResizeObserver(entries => { const box=entries[0].contentRect; setFrameSize({width:box.width,height:box.height}); });
    observer.observe(element); return ()=>observer.disconnect();
  }, [project?.id,clip?.aspect]);
  const working = Boolean(busy)""")
old="const p = await api<Project>('/projects', { method: 'POST', body: form });"
new="""setUploadProgress({loaded:0,total:uploadFile.size,stage:'uploading'});
    let p:Project;
    try { p = await new Promise<Project>((resolve,reject) => {
      const xhr=new XMLHttpRequest(); xhr.open('POST', `${API}/projects`);
      xhr.upload.onprogress=e=>{if(e.lengthComputable)setUploadProgress({loaded:e.loaded,total:e.total,stage:e.loaded>=e.total?'preparing':'uploading'});};
      xhr.upload.onload=()=>{setBusy('Preparing video');setUploadProgress(v=>v?{...v,loaded:v.total,stage:'preparing'}:v);};
      xhr.onload=()=>{let data;try{data=JSON.parse(xhr.responseText);}catch{reject(new Error('The server returned an unreadable upload response.'));return;}if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data)));};
      xhr.onerror=()=>reject(new Error('Upload connection failed. Check that the local server is running.')); xhr.onabort=()=>reject(new Error('Upload was cancelled.'));xhr.send(form);
    }); } finally { setUploadProgress(null); }
    """
assert old in s;s=s.replace(old,new)
s=s.replace("if (next.status === 'completed') { clearInterval(id); setNotice(next.message || 'Finished successfully'); if (activeProject.current) await refreshProject(activeProject.current); }", "if (next.status === 'completed') { clearInterval(id); setNotice(next.message || 'Finished successfully'); if (activeProject.current === next.project_id || !next.project_id) { if(activeProject.current) await refreshProject(activeProject.current); } else await loadProjects(); }")
s=s.replace("  const exported = project?.exports || [];", """  const exported = project?.exports || [];
  const scale=project?Math.max(frameSize.width/project.width,frameSize.height/project.height)*(clip?.zoom??1):1;
  const sourceWidth=(project?.width||1)*scale, sourceHeight=(project?.height||1)*scale;
  const videoStyle:CSSProperties=clip?.fit==='crop'?{position:'absolute',width:sourceWidth,height:sourceHeight,maxWidth:'none',left:-(sourceWidth-frameSize.width)*(clip.crop_x??.5),top:-(sourceHeight-frameSize.height)*(clip.crop_y??.5),objectFit:'fill'}:{width:'100%',height:'100%',objectFit:'contain'};
  const startStamp=job?.started_at||job?.created_at;
  const elapsed=startStamp?Math.max(0,Math.floor((clock-Date.parse(startStamp))/1000)):0;
  const uploadStatus=uploadProgress&&<div className="upload-progress" role="status"><div><strong>{uploadProgress.stage==='preparing'?'Preparing video':'Uploading video'}</strong><span>{uploadProgress.stage==='preparing'?'Reading metadata and creating a thumbnail':`${bytes(uploadProgress.loaded)} / ${bytes(uploadProgress.total)}`}</span></div><div className={`progress ${uploadProgress.stage==='preparing'?'indeterminate':''}`} role="progressbar" aria-label={uploadProgress.stage==='preparing'?'Preparing video':'Upload progress'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress.stage==='uploading'?Math.round(uploadProgress.loaded/Math.max(1,uploadProgress.total)*100):undefined}><span style={{width:uploadProgress.stage==='uploading'?`${uploadProgress.loaded/Math.max(1,uploadProgress.total)*100}%`:undefined}}/></div><small>{uploadProgress.stage==='preparing'?'Upload complete. Finishing local preparation…':`${Math.round(uploadProgress.loaded/Math.max(1,uploadProgress.total)*100)}% uploaded`}</small></div>;""")
s=s.replace("{error && <div className=\"alert error modal-error\" role=\"alert\">{error}</div>}{body}","{error && <div className=\"alert error modal-error\" role=\"alert\">{error}</div>}{body}")
s=s.replace("Your next great clip starts here.","Your video library.").replace("Ready for the world.","Finished videos.")
s=s.replace('CREATE MORE FROM WHAT YOU HAVE','YOUR WORKSPACE').replace('Turn your long videos into short stories worth watching.','Upload, find moments, edit, and download.').replace('No watermark. No upload limits from a subscription.','Local files. No watermark.')
s=s.replace("{job && ['queued','running'].includes(job.status) && <div className=\"job-bar\" role=\"status\"><LoaderCircle size={18} className=\"spin\"/><div><strong>{job.message || 'Working on your video…'}</strong><div className=\"progress\"><span style={{ width: `${Math.max(2, job.progress)}%` }}/></div></div><span>{Math.round(job.progress)}%</span></div>}", """{job && ['queued','running'].includes(job.status) && <div className="job-bar" role="status"><LoaderCircle size={21} className="spin"/><div><div className="job-title"><strong>{job.message || 'Waiting for the local worker'}</strong><span>{job.status === 'queued'?'Queued':`${time(elapsed)} elapsed`}</span></div><div className="progress" role="progressbar" aria-label="Processing progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><span style={{ width: `${Math.max(0,Math.min(100,job.progress))}%` }}/></div><small>Progress is reported by the worker. It can pause during model loading or analysis.</small></div><b>{Math.round(job.progress)}%</b></div>}""")
s=s.replace('<div className="studio-grid">','{project.analysis && <AnalysisPanel analysis={project.analysis}/>}<div className="studio-grid">')
s=s.replace('Find moments</button>', 'Analyze & find clips</button>')
s=s.replace('Find the strongest moments','Analyze the transcript')
s=s.replace('Suggestions use your saved transcript. Review the cuts before exporting—an AI suggestion is a starting point, not a promise of views.','Read the full saved transcript, create a summary, and suggest clips. Review the suggested cuts before exporting.')
s=s.replace('Qwen2.5 7B is a good starting point. No model is downloaded here.','Qwen3.5 9B is your default. Only an already-installed model is used.')
s=s.replace('JSON.stringify({provider,model,min_duration:minDuration,max_duration:maxDuration,count})','JSON.stringify({provider,model,min_duration:minDuration,max_duration:maxDuration,count,use_web_search:provider===\'ollama\'&&useWebSearch})')
s=s.replace("{!project?.segments.length&&<p", "{provider==='ollama'&&<label className=\"checkbox-field\"><input type=\"checkbox\" checked={useWebSearch} disabled={!health?.tavily_configured} onChange={e=>setUseWebSearch(e.target.checked)}/><span>Add web context with Tavily<small>{health?.tavily_configured?'Sends short topic queries to Tavily, not your video or full transcript.':'Optional: set TAVILY_API_KEY in the server environment, then restart.'}</small></span></label>}{!project?.segments.length&&<p",1)
s=s.replace("JSON.stringify({model:whisperModel,language:language.trim()||undefined,allow_download:allowDownload})", "JSON.stringify({model:whisperModel,language:language.trim()||undefined,allow_download:allowDownload,device,cpu_threads:cpuThreads})")
s=s.replace('<label className="field">Language code',"<div className=\"field-row\"><label className=\"field\">Processing device<select value={device} onChange={e=>setDevice(e.target.value as typeof device)}><option value=\"auto\">Auto · prefer GPU</option><option value=\"cuda\" disabled={!health?.transcription_gpu_available}>NVIDIA GPU</option><option value=\"cpu\">CPU</option></select></label><label className=\"field\">CPU threads<input type=\"number\" min=\"1\" max=\"32\" value={cpuThreads} onChange={e=>setCpuThreads(Number(e.target.value))}/></label></div><p className=\"hint\">{health?.transcription_gpu_available?'NVIDIA GPU detected. Auto can use CUDA for faster transcription.':'GPU transcription is unavailable; Auto uses the CPU.'}</p><label className=\"field\">Language code")
s=s.replace('A model must be available locally before transcription can run.','Choose a cached model, or explicitly allow a model download below.')
s=s.replace("{busy==='Uploading video'?<LoaderCircle", "{uploadProgress?<LoaderCircle")
s=s.replace("{busy==='Uploading video'?'Importing…':'Create project'}", "{uploadProgress?(uploadProgress.stage==='uploading'?'Uploading…':'Preparing…'):'Create project'}")
s=s.replace('<label className="field">Project title', '{uploadStatus}<label className="field">Project title')
s=s.replace('className="upload-zone ${uploadFile?', 'className="upload-zone ${uploadFile?')
s=s.replace('<div className={`video-frame ${clip?.fit', '<div ref={frame} className={`video-frame ${clip?.fit')
s=s.replace('controls playsInline preload="metadata"', 'playsInline preload="metadata" onPause={()=>setIsPlaying(false)}')
s=s.replace('onPlay={e => { if(clip', 'onPlay={e => { setIsPlaying(true); if(clip')
old="style={{objectFit:clip?.fit === 'contain' ? 'contain' : 'cover',objectPosition:`${(clip?.crop_x ?? .5)*100}% center`}}"
assert old in s;s=s.replace(old,"style={videoStyle}")
s=s.replace('Framing & caption preview · Exported MP4 is the final render','Crop matches your export. Caption rendering is approximate.')
s=s.replace('<div className="preview-note">', '<div className="playback-controls"><button className="button small" aria-label={isPlaying?\'Pause preview\':\'Play preview\'} onClick={()=>{if(video.current){if(video.current.paused)video.current.play().catch(e=>setError(e.message));else video.current.pause();}}}>{isPlaying?<Pause size={16}/>:<Play size={16}/>} {isPlaying?\'Pause\':\'Play\'}</button><span>{time(currentTime)} / {time(project.duration)}</span></div><div className="preview-note">')
old="{clip.fit==='crop'&&<label className=\"field\">Horizontal focus <span className=\"range-labels\"><span>Left</span><span>Right</span></span><input type=\"range\" min=\"0\" max=\"1\" step=\"0.01\" value={clip.crop_x} onChange={e=>updateClip('crop_x',Number(e.target.value))}/></label>}"
new="""{clip.fit==='crop'&&<div className="crop-controls"><div className="crop-heading"><strong>Crop position</strong><button className="button small" onClick={()=>{setClip({...clip,crop_x:.5,crop_y:.5,zoom:1});setDirtyClip(true);}}><RotateCcw size={13}/> Reset</button></div><label className="field">Horizontal <span className="range-labels"><span>Left</span><span>Right</span></span><input aria-label="Horizontal crop" type="range" min="0" max="1" step="0.01" value={clip.crop_x} onChange={e=>updateClip('crop_x',Number(e.target.value))}/></label><label className="field">Vertical <span className="range-labels"><span>Top</span><span>Bottom</span></span><input aria-label="Vertical crop" type="range" min="0" max="1" step="0.01" value={clip.crop_y??.5} onChange={e=>updateClip('crop_y',Number(e.target.value))}/></label><label className="field">Zoom <span>{(clip.zoom??1).toFixed(2)}×</span><input aria-label="Crop zoom" type="range" min="1" max="3" step="0.05" value={clip.zoom??1} onChange={e=>updateClip('zoom',Number(e.target.value))}/></label><p className="hint">Drag the preview to reposition the image.</p></div>}"""
assert old in s;s=s.replace(old,new)
# Pointer handling is on the frame, and caption overlays are pointer-transparent.
s=s.replace('<div ref={frame} className=', """<div ref={frame} onPointerDown={e=>{if(clip?.fit!=='crop')return;cropDrag.current={x:e.clientX,y:e.clientY,cropX:clip.crop_x,cropY:clip.crop_y??.5};e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{const d=cropDrag.current;if(!d||!clip)return;const dx=sourceWidth-frameSize.width,dy=sourceHeight-frameSize.height;setClip({...clip,crop_x:dx>.1?Math.max(0,Math.min(1,d.cropX-(e.clientX-d.x)/dx)):clip.crop_x,crop_y:dy>.1?Math.max(0,Math.min(1,d.cropY-(e.clientY-d.y)/dy)):(clip.crop_y??.5)});setDirtyClip(true);}} onPointerUp={()=>{cropDrag.current=null;}} onPointerCancel={()=>{cropDrag.current=null;}} className=""")
# Simplify visible copy, retain no added external connections.
s=s.replace('Make it yours','Clip settings').replace('Your edit, your way.','Choose a clip.').replace('One video.<br/>So many possibilities.','Start with a video.').replace('FROM LONG-FORM TO STANDOUT','LOCAL VIDEO EDITOR')
s=s.replace('MAKE EVERY MOMENT COUNT.','YOUR NEXT CLIP').replace('Built for the moments worth keeping.','Upload. Edit. Download.')
s=s.replace('No social integrations, automatic publishing, or cloud uploads.','No social integrations or cloud uploads. Optional Tavily search is used only when you enable it.')
p.write_text(s,encoding='utf-8')
