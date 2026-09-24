/**
 * Photos: authenticated display, a lightbox with zoom, and the uploader.
 *
 * Issue photos can show the inside of a laboratory, so they are not public
 * files: every image is fetched with the session token and shown from a
 * short-lived object URL.
 */
import { DragEvent, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ChevronLeft, ChevronRight, Download, ImagePlus, Minus, Plus, Trash2, X,
} from 'lucide-react'
import { fetchBlob } from '../lib/api'

export function AuthImage({ path, alt, className = '', onClick }: {
  path: string; alt: string; className?: string; onClick?: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let revoked = false
    let obj: string | null = null
    setUrl(null); setFailed(false)
    fetchBlob(path)
      .then(b => {
        if (revoked) return
        obj = URL.createObjectURL(b)
        setUrl(obj)
      })
      .catch(() => { if (!revoked) setFailed(true) })
    return () => { revoked = true; if (obj) URL.revokeObjectURL(obj) }
  }, [path])

  if (failed) {
    return <div className={`grid place-items-center bg-ink-800 text-[11px] text-slate-400
                            ${className}`}>Unavailable</div>
  }
  if (!url) return <div className={`skeleton ${className}`} />
  return <img src={url} alt={alt} className={`object-cover ${className}`}
              onClick={onClick} draggable={false} />
}

export interface GalleryPhoto {
  id: number
  thumbPath: string
  fullPath: string
  downloadPath: string
  caption: string
}

export function Lightbox({ photos, index, onClose, onIndex }: {
  photos: GalleryPhoto[]; index: number | null; onClose: () => void
  onIndex: (i: number) => void
}) {
  const [zoom, setZoom] = useState(1)
  useEffect(() => { setZoom(1) }, [index])
  useEffect(() => {
    if (index === null) return
    const k = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') onIndex((index + 1) % photos.length)
      if (e.key === 'ArrowLeft') onIndex((index - 1 + photos.length) % photos.length)
      if (e.key === '+') setZoom(z => Math.min(4, z + .5))
      if (e.key === '-') setZoom(z => Math.max(1, z - .5))
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [index, photos.length, onClose, onIndex])

  async function download(p: GalleryPhoto) {
    const blob = await fetchBlob(p.downloadPath)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = p.caption.replace(/[^\w.-]+/g, '_') || 'photo'
    a.click()
    URL.revokeObjectURL(url)
  }

  const p = index !== null ? photos[index] : null
  return (
    <AnimatePresence>
      {p && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] bg-ink-950/95 backdrop-blur flex flex-col"
          role="dialog" aria-modal="true" aria-label="Photo viewer">
          <div className="flex items-center justify-between gap-3 px-4 py-3
                          border-b border-ink-700">
            <div className="text-sm text-slate-200 truncate">{p.caption}
              <span className="text-slate-500"> · {index! + 1} / {photos.length}</span>
            </div>
            <div className="flex items-center gap-1">
              <button className="btn-quiet !p-2" aria-label="Zoom out"
                      onClick={() => setZoom(z => Math.max(1, z - .5))}><Minus size={16} /></button>
              <span className="mono text-slate-400 w-10 text-center">{Math.round(zoom * 100)}%</span>
              <button className="btn-quiet !p-2" aria-label="Zoom in"
                      onClick={() => setZoom(z => Math.min(4, z + .5))}><Plus size={16} /></button>
              <button className="btn-quiet !p-2" aria-label="Download original"
                      onClick={() => download(p)}><Download size={16} /></button>
              <button className="btn-quiet !p-2" aria-label="Close" onClick={onClose}>
                <X size={18} /></button>
            </div>
          </div>
          <div className="relative flex-1 overflow-auto grid place-items-center p-4"
               onClick={e => { if (e.target === e.currentTarget) onClose() }}>
            <div style={{ transform: `scale(${zoom})`, transformOrigin: 'center' }}
                 className="transition-transform duration-150">
              <AuthImage path={p.fullPath} alt={p.caption}
                         className="max-h-[78vh] max-w-[92vw] !object-contain rounded-lg" />
            </div>
            {photos.length > 1 && (
              <>
                <button aria-label="Previous photo"
                  onClick={() => onIndex((index! - 1 + photos.length) % photos.length)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 btn-ghost !p-2.5 !rounded-full">
                  <ChevronLeft size={18} /></button>
                <button aria-label="Next photo"
                  onClick={() => onIndex((index! + 1) % photos.length)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 btn-ghost !p-2.5 !rounded-full">
                  <ChevronRight size={18} /></button>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// --- uploader ----------------------------------------------------------------
const ACCEPT = ['image/jpeg', 'image/png', 'image/webp']

export interface PickedFile { id: string; file: File; url: string; error?: string }

/**
 * Drag-and-drop or pick, with previews and removal before anything is sent.
 * Type and size are checked here for fast feedback only; the server decodes
 * every file and is the one that decides.
 */
export function PhotoPicker({ files, onChange, maxFiles = 6, maxMb = 12, disabled = false }: {
  files: PickedFile[]; onChange: (f: PickedFile[]) => void
  maxFiles?: number; maxMb?: number; disabled?: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [note, setNote] = useState('')

  // Free preview URLs when the component goes away.
  const urls = useRef<string[]>([])
  urls.current = files.map(f => f.url)
  useEffect(() => () => urls.current.forEach(u => URL.revokeObjectURL(u)), [])

  function add(list: FileList | File[]) {
    setNote('')
    const next = [...files]
    const rejected: string[] = []
    for (const file of Array.from(list)) {
      if (next.length >= maxFiles) { rejected.push(`${file.name}: limit of ${maxFiles} photos`); continue }
      if (!ACCEPT.includes(file.type)) { rejected.push(`${file.name}: not JPEG, PNG or WebP`); continue }
      if (file.size > maxMb * 1024 * 1024) { rejected.push(`${file.name}: larger than ${maxMb} MB`); continue }
      next.push({ id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
                  file, url: URL.createObjectURL(file) })
    }
    if (rejected.length) setNote(rejected.join(' · '))
    onChange(next)
  }

  function remove(id: string) {
    const f = files.find(x => x.id === id)
    if (f) URL.revokeObjectURL(f.url)
    onChange(files.filter(x => x.id !== id))
  }

  function drop(e: DragEvent) {
    e.preventDefault(); setOver(false)
    if (!disabled && e.dataTransfer.files.length) add(e.dataTransfer.files)
  }

  return (
    <div>
      <div
        onDragOver={e => { e.preventDefault(); if (!disabled) setOver(true) }}
        onDragLeave={() => setOver(false)} onDrop={drop}
        onClick={() => !disabled && input.current?.click()}
        role="button" tabIndex={0} aria-disabled={disabled}
        onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && !disabled) input.current?.click() }}
        className={`rounded-xl border-2 border-dashed px-4 py-6 text-center cursor-pointer
                    transition-colors ${over ? 'border-accent-400 bg-accent-500/10'
                    : 'border-ink-500 hover:border-ink-400 bg-ink-900/40'}
                    ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}>
        <ImagePlus size={22} className="mx-auto text-accent-300" />
        <div className="mt-2 text-sm text-slate-200">
          Drop photos here or <span className="text-accent-300 underline underline-offset-2">choose files</span>
        </div>
        <div className="mt-1 text-xs text-slate-400">
          JPEG, PNG or WebP · up to {maxMb} MB each · {maxFiles} max. On a phone you can take the photo directly.
        </div>
        <input ref={input} type="file" accept={ACCEPT.join(',')} multiple hidden
               onChange={e => { if (e.target.files) add(e.target.files); e.target.value = '' }} />
      </div>
      {note && <p className="mt-2 text-xs text-warn-soft">{note}</p>}
      {files.length > 0 && (
        <ul className="mt-3 grid grid-cols-3 sm:grid-cols-4 gap-2.5">
          {files.map(f => (
            <li key={f.id} className="relative group rounded-lg overflow-hidden border
                                      border-ink-600 aspect-square bg-ink-900">
              <img src={f.url} alt={f.file.name} className="w-full h-full object-cover" />
              <div className="absolute inset-x-0 bottom-0 px-1.5 py-1 bg-ink-950/80
                              text-[10px] text-slate-300 truncate">
                {(f.file.size / 1024 / 1024).toFixed(1)} MB
              </div>
              {!disabled && (
                <button onClick={() => remove(f.id)} aria-label={`Remove ${f.file.name}`}
                  className="absolute top-1.5 right-1.5 grid place-items-center w-7 h-7
                             rounded-md bg-ink-950/85 text-slate-200 hover:text-bad-soft">
                  <Trash2 size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
