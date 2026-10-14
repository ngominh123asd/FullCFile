import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Image as ImageIcon,
  Sliders,
  Zap,
  Globe,
  FileType2,
  Plus,
  X,
  CheckCircle2,
  AlertCircle,
  Download,
  Cpu,
  Timer,
} from 'lucide-react'
import { Button } from '../ui/button'

// Map file extension → MIME type for download Blobs.
const MIME_MAP: Record<string, string> = {
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  txt: 'text/plain;charset=utf-8',
  html: 'text/html;charset=utf-8',
  csv: 'text/csv;charset=utf-8',
  json: 'application/json;charset=utf-8',
}
const getMimeType = (fmt: string): string => MIME_MAP[fmt.toLowerCase()] || 'application/octet-stream'
import DropZone from '../ui/dropzone'
import { ocrApi, filesApi, jobsApi } from '../../lib/api'
import { Job, OcrOptions } from '../../types'
import { formatBytes, parseServerDate } from '../../lib/utils'
import toast from 'react-hot-toast'

export interface StagedOcrItem {
  id?: string
  name: string
  size: number
  rawFile?: File
}

interface OcrStudioProps {
  initialFiles?: any[]
  onJobCreated: (job: Job) => void
}

export default function OcrStudio({ initialFiles, onJobCreated }: OcrStudioProps) {
  const [selectedFiles, setSelectedFiles] = useState<StagedOcrItem[]>([])
  const [outputFormat, setOutputFormat] = useState<'docx' | 'xlsx' | 'pdf' | 'txt' | 'html'>('docx')
  const [engine, setEngine] = useState<'fast_native' | 'vietocr'>('fast_native')
  const [language, setLanguage] = useState<'vi' | 'en' | 'auto'>(() => {
    const saved = localStorage.getItem('fileforge_default_ocr_lang')
    return saved === 'en' || saved === 'auto' || saved === 'vi' ? saved : 'vi'
  })
  const [useGpu, setUseGpu] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [finalDuration, setFinalDuration] = useState<number | null>(null)
  const startTimeRef = useRef<number | null>(null)
  const activeJobIdRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Batch progress & results
  const [batchProgress, setBatchProgress] = useState<{
    total: number
    current: number
    currentFilename: string
    percent: number
    stageText: string
    successCount: number
    failedCount: number
  } | null>(null)
  const [batchResults, setBatchResults] = useState<Array<{
    file: StagedOcrItem
    job?: Job
    error?: string
    status: 'completed' | 'failed'
  }> | null>(null)

  const allOcrFormats: Array<{ id: 'docx' | 'xlsx' | 'pdf' | 'txt' | 'html'; label: string }> = [
    { id: 'docx', label: 'DOCX' },
    { id: 'xlsx', label: 'XLSX' },
    { id: 'pdf', label: 'PDF' },
    { id: 'txt', label: 'TXT' },
    { id: 'html', label: 'HTML' },
  ]

  // Restore running OCR job across page reloads
  useEffect(() => {
    const checkRunningJob = async () => {
      let activeJob: any = null
      let savedMeta: any = null

      const savedRaw = localStorage.getItem('fileforge_active_ocr')
      if (savedRaw) {
        try {
          savedMeta = JSON.parse(savedRaw)
          if (savedMeta && savedMeta.jobId) {
            const res = await jobsApi.get(savedMeta.jobId)
            activeJob = res.data
          }
        } catch {
          // ignore
        }
      }

      if (!activeJob) {
        try {
          const listRes = await jobsApi.list({ status: 'processing', job_type: 'ocr', limit: 1 })
          if (listRes.data && listRes.data.length > 0) {
            activeJob = listRes.data[0]
          }
        } catch {
          // ignore
        }
      }

      if (activeJob && (activeJob.status === 'processing' || activeJob.status === 'pending')) {
        setIsProcessing(true)
        activeJobIdRef.current = activeJob.id
        const startTime = savedMeta?.startedAt || (activeJob.started_at ? parseServerDate(activeJob.started_at).getTime() : Date.now())
        startTimeRef.current = startTime
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startTime) / 1000)))
        const restoreFileName = savedMeta?.filename || activeJob.input_filename || 'Tài liệu đang xử lý'
        setSelectedFiles([
          {
            name: restoreFileName,
            size: savedMeta?.fileSize || 0,
            id: activeJob.input_file_id,
          },
        ])
        setBatchProgress({
          total: 1,
          current: 0,
          currentFilename: restoreFileName,
          percent: activeJob.progress || 5,
          stageText: activeJob.stage || 'Đang tiếp tục nhận diện...',
          successCount: 0,
          failedCount: 0,
        })

        const pollInterval = setInterval(async () => {
          try {
            const pollRes = await jobsApi.get(activeJob.id)
            const current = pollRes.data
            if (current.status === 'completed') {
              clearInterval(pollInterval)
              localStorage.removeItem('fileforge_active_ocr')
              activeJobIdRef.current = null
              setIsProcessing(false)
              setBatchProgress(null)
              setFinalDuration(Math.max(1, Math.floor((Date.now() - startTime) / 1000)))
              setBatchResults([
                {
                  file: { name: current.input_filename || restoreFileName, size: savedMeta?.fileSize || 0 },
                  job: current,
                  status: 'completed',
                },
              ])
              onJobCreated(current)
              toast.success('Bóc tách OCR hoàn tất thành công!')
            } else if (current.status === 'failed') {
              clearInterval(pollInterval)
              localStorage.removeItem('fileforge_active_ocr')
              activeJobIdRef.current = null
              setIsProcessing(false)
              setBatchProgress(null)
              toast.error(current.error || 'Lỗi xử lý OCR')
            } else {
              setBatchProgress((prev) =>
                prev ? { ...prev, percent: current.progress || prev.percent, stageText: current.stage || prev.stageText } : null
              )
            }
          } catch {
            // ignore transient error
          }
        }, 1500)

        return () => clearInterval(pollInterval)
      } else {
        localStorage.removeItem('fileforge_active_ocr')
      }
    }

    checkRunningJob()
  }, [])

  useEffect(() => {
    if (initialFiles && initialFiles.length > 0) {
      const mapped: StagedOcrItem[] = initialFiles.map((f: any) => ({
        id: f.id,
        name: f.original_filename || f.name || 'image.png',
        size: f.file_size || f.size || 0,
        rawFile: f instanceof File ? f : undefined,
      }))
      setSelectedFiles(mapped)
      setBatchResults(null)
    } else {
      if (!isProcessing) {
        setSelectedFiles([])
        setBatchResults(null)
      }
    }
  }, [initialFiles])

  // Live elapsed-time ticker
  useEffect(() => {
    if (!isProcessing) return
    const tick = () => {
      if (startTimeRef.current) {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [isProcessing])

  const handleFiles = (files: File[], isPaste = false) => {
    if (files.length > 0) {
      const newItems: StagedOcrItem[] = files.map((f) => ({
        name: f.name,
        size: f.size,
        rawFile: f,
      }))
      setSelectedFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name))
        const filtered = newItems.filter((f) => !existingNames.has(f.name))
        return [...prev, ...filtered]
      })
      setBatchResults(null)
      if (!isPaste) {
        toast.success(
          files.length === 1
            ? `Đã thêm: ${files[0].name}`
            : `Đã thêm ${files.length} tệp vào hàng đợi OCR!`
        )
      }
    }
  }

  // Ctrl + V clipboard paste support
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items || items.length === 0) return

      const isTextInput =
        document.activeElement instanceof HTMLInputElement ||
        document.activeElement instanceof HTMLTextAreaElement
      if (isTextInput) return

      const imageFiles: File[] = []

      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            const ext = blob.type.split('/')[1]?.replace('jpeg', 'jpg') || 'png'
            const now = new Date()
            const timeStr = `${String(now.getHours()).padStart(2, '0')}${String(
              now.getMinutes()
            ).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`
            const filename = `screenshot_${timeStr}.${ext}`
            const renamedFile = new File([blob], filename, { type: blob.type })
            imageFiles.push(renamedFile)
          }
        }
      }

      if (imageFiles.length === 0 && e.clipboardData?.files?.length) {
        for (let i = 0; i < e.clipboardData.files.length; i++) {
          const f = e.clipboardData.files[i]
          if (
            f.type.startsWith('image/') ||
            ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'bmp', 'pdf'].some((ext) =>
              f.name.toLowerCase().endsWith('.' + ext)
            )
          ) {
            imageFiles.push(f)
          }
        }
      }

      if (imageFiles.length > 0) {
        e.preventDefault()
        handleFiles(imageFiles, true)
        toast.success(
          imageFiles.length === 1
            ? `Đã dán ảnh "${imageFiles[0].name}" (Ctrl + V)!`
            : `Đã dán ${imageFiles.length} ảnh từ Clipboard!`
        )
      }
    }

    window.addEventListener('paste', handlePaste)
    return () => window.removeEventListener('paste', handlePaste)
  }, [])

  const handleClear = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    const currentJobId = activeJobIdRef.current
    activeJobIdRef.current = null
    localStorage.removeItem('fileforge_active_ocr')
    setIsProcessing(false)
    setBatchProgress(null)
    startTimeRef.current = null
    setElapsedSeconds(0)
    setSelectedFiles([])
    setBatchResults(null)

    if (currentJobId) {
      try {
        await ocrApi.cancel(currentJobId)
      } catch {
        try {
          await jobsApi.delete(currentJobId)
        } catch {}
      }
    }

    toast.success('Đã xóa hàng đợi OCR!')
  }

  const removeFile = (index: number) => {
    if (isProcessing) {
      handleClear()
      return
    }
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleRunOcr = async () => {
    if (selectedFiles.length === 0) {
      toast.error('Vui lòng chọn hoặc kéo thả ảnh cần OCR')
      return
    }

    setIsProcessing(true)
    abortControllerRef.current = new AbortController()
    startTimeRef.current = Date.now()
    setElapsedSeconds(0)
    setFinalDuration(null)
    setBatchProgress({
      total: selectedFiles.length,
      current: 0,
      currentFilename: selectedFiles[0].name,
      percent: 5,
      stageText: 'Đang chuẩn bị...',
      successCount: 0,
      failedCount: 0,
    })
    setBatchResults([])

    const results: Array<{
      file: StagedOcrItem
      job?: Job
      error?: string
      status: 'completed' | 'failed'
    }> = []

    for (let i = 0; i < selectedFiles.length; i++) {
      if (abortControllerRef.current?.signal.aborted) break

      const file = selectedFiles[i]
      const basePercent = Math.round((i / selectedFiles.length) * 100)
      const perFileSpan = Math.round(100 / selectedFiles.length)

      setBatchProgress({
        total: selectedFiles.length,
        current: i,
        currentFilename: file.name,
        percent: Math.min(99, basePercent + 1),
        stageText: 'Đang nạp tệp lên máy chủ AI...',
        successCount: results.filter((r) => r.status === 'completed').length,
        failedCount: results.filter((r) => r.status === 'failed').length,
      })

      try {
        let inputFileId = file.id
        if (!inputFileId && file.rawFile) {
          const uploadRes = await filesApi.upload([file.rawFile])
          inputFileId = uploadRes.data.files[0].id
        }
        if (!inputFileId) throw new Error('Không tìm thấy mã tệp tin')

        const ocrOptions: OcrOptions = {
          engine,
          language,
          preserve_layout: true,
          preserve_tables: true,
          use_gpu: useGpu,
        }

        let job: Job
        try {
          job = await ocrApi.processStream(
            {
              input_file_id: inputFileId,
              output_format: outputFormat,
              ...ocrOptions,
            },
            (realProgress, realStage, streamJobId) => {
              if (streamJobId && activeJobIdRef.current !== streamJobId) {
                activeJobIdRef.current = streamJobId
                localStorage.setItem(
                  'fileforge_active_ocr',
                  JSON.stringify({
                    jobId: streamJobId,
                    filename: file.name,
                    fileSize: file.size,
                    startedAt: startTimeRef.current,
                    format: outputFormat,
                  })
                )
              }
              const fileLocalPercent = Math.min(100, Math.max(0, realProgress))
              const overallPercent = Math.min(100, Math.round(basePercent + (fileLocalPercent / 100) * perFileSpan))
              setBatchProgress((prev) => {
                if (!prev) return null
                return { ...prev, percent: overallPercent, stageText: realStage }
              })
            },
            abortControllerRef.current?.signal
          )
        } catch (streamErr: any) {
          if (streamErr.name === 'AbortError' || abortControllerRef.current?.signal.aborted) return
          const res = await ocrApi.process({
            input_file_id: inputFileId,
            output_format: outputFormat,
            ...ocrOptions,
          })
          job = res.data
        }

        setBatchProgress((prev) =>
          prev ? { ...prev, percent: Math.min(100, basePercent + perFileSpan), stageText: `Đã hoàn tất xuất tệp ${outputFormat.toUpperCase()}!` } : null
        )

        if (job.status === 'completed') {
          results.push({ file, job, status: 'completed' })
          onJobCreated(job)
        } else {
          results.push({ file, job, error: job.error || 'Lỗi OCR', status: 'failed' })
        }
      } catch (err: any) {
        if (err.name === 'AbortError' || abortControllerRef.current?.signal.aborted) return
        results.push({ file, error: err.response?.data?.detail || err.message || 'Lỗi xử lý OCR', status: 'failed' })
      }
    }

    if (abortControllerRef.current?.signal.aborted) return

    const successCount = results.filter((r) => r.status === 'completed').length
    const failedCount = results.filter((r) => r.status === 'failed').length

    const totalSec = startTimeRef.current ? Math.floor((Date.now() - startTimeRef.current) / 1000) : elapsedSeconds
    setFinalDuration(totalSec)
    setBatchResults(results)
    setIsProcessing(false)
    setBatchProgress(null)
    startTimeRef.current = null
    activeJobIdRef.current = null
    abortControllerRef.current = null
    localStorage.removeItem('fileforge_active_ocr')

    if (successCount === selectedFiles.length) {
      toast.success(`Đã bóc tách OCR thành công tất cả ${successCount} tệp!`)
    } else if (successCount > 0) {
      toast.success(`Hoàn tất: ${successCount} thành công, ${failedCount} thất bại`)
    } else {
      toast.error(`Bóc tách OCR thất bại cho ${failedCount} tệp`)
    }
  }

  const handleDownloadAll = async () => {
    if (!batchResults) return
    const completed = batchResults.filter((r) => r.status === 'completed' && r.job)
    if (completed.length === 0) return

    toast.success(`Bắt đầu tải về ${completed.length} tệp OCR...`)
    for (let i = 0; i < completed.length; i++) {
      const item = completed[i]
      if (item.job) {
        try {
          const res = await jobsApi.download(item.job.id)
          const actualFmt = item.job.result?.format || outputFormat
          const mime = getMimeType(actualFmt)
          const blob = new Blob([res.data], { type: mime })
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `ocr_${item.file.name.replace(/\.[^/.]+$/, '')}.${actualFmt}`
          a.click()
          window.URL.revokeObjectURL(url)
          await new Promise((resolve) => setTimeout(resolve, 350))
        } catch {}
      }
    }
  }

  return (
    <div className="zzz-device-frame p-5 sm:p-7 space-y-6 shadow-2xl">
      {/* Studio Header - ZZZ In-Game Hardware Bezel */}
      <div className="flex items-center justify-between border-b border-[#282B37] pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-[#B8E900] flex-shrink-0">
            <ImageIcon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-bold font-tech uppercase tracking-wider text-white">
              VISION OCR LAB // KIẾN TRÚC ĐA CHẾ ĐỘ
            </h3>
            <p className="text-xs font-mono text-[#9CA3AF]">
              Tối ưu hóa CPU siêu tốc Native OCR hoặc Deep Learning VietOCR Transformer chuyên sâu
            </p>
          </div>
        </div>

        <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono bg-[#222530] text-white border border-[#2E313E]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900] animate-pulse" />
          <span>DUAL-ENGINE ACTIVE</span>
        </span>
      </div>

      {/* Upload Zone / Staged Cockpit */}
      {selectedFiles.length === 0 ? (
        <DropZone
          onFilesSelected={handleFiles}
          isLoading={isProcessing}
          maxFiles={50}
          acceptTypes={['.png', '.jpg', '.jpeg', '.tiff', '.webp', '.pdf']}
          helperText="Kéo thả hoặc chọn nhiều ảnh scan (.png, .jpg, .jpeg, .webp, .tiff) hoặc tài liệu PDF dạng ảnh. Hỗ trợ dán trực tiếp ảnh chụp (Ctrl + V)."
        />
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="space-y-6"
        >
          {/* Staging Cockpit Frame */}
          <div className="rounded-2xl bg-[#14151C] border border-[#282B37] p-5 sm:p-6 space-y-5">
            {/* Staged Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#282B37]">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white flex-shrink-0">
                  <FileType2 className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold font-tech uppercase tracking-wider text-white">
                      HÀNG ĐỢI OCR ({selectedFiles.length} TỆP TIN)
                    </h4>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#222530] text-[#B8E900] border border-[#2E313E]">
                      BATCH
                    </span>
                  </div>
                  <p className="text-xs font-mono text-[#9CA3AF] mt-0.5">
                    Tổng dung lượng: {formatBytes(selectedFiles.reduce((acc, f) => acc + (f.size || 0), 0))}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
                <label className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase bg-[#222530] hover:bg-[#2B2E3C] text-white border border-[#2E313E] hover:border-white transition-colors">
                  <Plus className="w-3.5 h-3.5" />
                  <span>THÊM ẢNH</span>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.tiff,.webp,.pdf"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        handleFiles(Array.from(e.target.files))
                      }
                    }}
                  />
                </label>
                <button
                  type="button"
                  onClick={handleClear}
                  className="px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase bg-[#2A1518] text-[#FF4D6D] hover:bg-[#381B20] border border-[#FF4D6D]/30 transition-colors"
                >
                  XÓA TẤT CẢ
                </button>
              </div>
            </div>

            {/* Queue files list (ZZZ Tactile Dark Tiles) */}
            <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1 custom-scrollbar">
              {selectedFiles.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-xl bg-[#222530] border border-[#2E313E] text-xs font-mono hover:border-[#3D4255] transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-6 h-6 rounded-lg bg-[#181A22] border border-[#282B37] flex items-center justify-center text-[10px] text-white font-bold flex-shrink-0">
                      {idx + 1}
                    </span>
                    <span className="text-white truncate font-semibold">{file.name}</span>
                    <span className="text-[#6B7280]">({formatBytes(file.size)})</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(idx)}
                    className="p-1 rounded-lg text-[#9CA3AF] hover:text-[#FF3355] hover:bg-white/5 transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            {/* OCR Options Matrix (Screenshot 1 & 3: Tactile Dark Tiles) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
              {/* 1. Output Format */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#B8E900]" /> 1. ĐỊNH DẠNG XUẤT
                </label>
                <div className="grid grid-cols-2 gap-1.5">
                  {allOcrFormats.map((fmt) => {
                    const isSelected = outputFormat === fmt.id
                    return (
                      <button
                        key={fmt.id}
                        type="button"
                        onClick={() => setOutputFormat(fmt.id)}
                        className={`py-2 px-2 rounded-xl text-xs font-tech font-bold uppercase transition-all text-center ${
                          isSelected
                            ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                            : 'bg-[#222530] text-[#9CA3AF] hover:text-white border border-[#2E313E]'
                        }`}
                      >
                        {fmt.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 2. OCR Engine Selection */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-[#B8E900]" /> 2. CHẾ ĐỘ ENGINE
                </label>
                <div className="space-y-2">
                  {[
                    { id: 'fast_native', name: 'Native C++ (Siêu Tốc)', desc: 'CPU ~10-15s • Khuyên dùng' },
                    { id: 'vietocr', name: 'VietOCR Transformer', desc: 'Deep Learning chuyên sâu' },
                  ].map((eng) => {
                    const isSelected = engine === eng.id
                    return (
                      <button
                        key={eng.id}
                        type="button"
                        onClick={() => setEngine(eng.id as any)}
                        className={`w-full p-2 rounded-xl text-xs text-left transition-all border ${
                          isSelected
                            ? 'bg-[#222530] border-[#B8E900] text-white shadow-[0_0_10px_rgba(184,233,0,0.15)]'
                            : 'bg-[#222530] border-[#2E313E] text-[#9CA3AF] hover:text-white'
                        }`}
                      >
                        <div className="font-tech font-bold uppercase flex items-center justify-between">
                          <span>{eng.name}</span>
                          {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />}
                        </div>
                        <div className="text-[10px] font-mono text-[#6B7280] mt-0.5">{eng.desc}</div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 3. OCR Language */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-[#B8E900]" /> 3. NGÔN NGỮ OCR
                </label>
                <div className="space-y-1.5">
                  {[
                    { id: 'vi', label: 'Tiếng Việt (Có dấu)' },
                    { id: 'en', label: 'English (Latin)' },
                    { id: 'auto', label: 'Tự động (Auto)' },
                  ].map((l) => {
                    const isSelected = language === l.id
                    return (
                      <button
                        key={l.id}
                        type="button"
                        onClick={() => setLanguage(l.id as any)}
                        className={`w-full py-1.5 px-3 rounded-xl text-xs font-tech font-bold uppercase text-left transition-all border flex items-center justify-between ${
                          isSelected
                            ? 'bg-[#222530] border-[#B8E900] text-white'
                            : 'bg-[#222530] border-[#2E313E] text-[#9CA3AF] hover:text-white'
                        }`}
                      >
                        <span>{l.label}</span>
                        {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 4. Hardware Acceleration */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-[#B8E900]" /> 4. TĂNG TỐC PHẦN CỨNG
                  </label>
                  <span
                    className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                      useGpu ? 'bg-[#222530] text-[#B8E900] border border-[#B8E900]' : 'bg-[#222530] text-[#6B7280] border border-[#2E313E]'
                    }`}
                  >
                    {useGpu ? 'GPU' : 'CPU'}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <button
                    type="button"
                    onClick={() => setUseGpu(false)}
                    className={`w-full py-1.5 px-3 rounded-xl text-xs text-left transition-all border flex items-center justify-between ${
                      !useGpu
                        ? 'bg-[#222530] border-[#B8E900] text-white'
                        : 'bg-[#222530] border-[#2E313E] text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    <div>
                      <div className="font-tech font-bold uppercase text-white">CPU TIÊU CHUẨN</div>
                      <div className="text-[10px] font-mono text-[#6B7280]">Đa luồng OpenMP • Ổn định</div>
                    </div>
                    {!useGpu && <div className="w-2 h-2 rounded-full bg-[#B8E900]" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => setUseGpu(!useGpu)}
                    className={`w-full py-1.5 px-3 rounded-xl text-xs text-left transition-all border flex items-center justify-between ${
                      useGpu
                        ? 'bg-[#222530] border-[#B8E900] text-white'
                        : 'bg-[#222530] border-[#2E313E] text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    <div>
                      <div className="font-tech font-bold uppercase text-white">TĂNG TỐC GPU CUDA</div>
                      <div className="text-[10px] font-mono text-[#6B7280]">Tăng tốc độ trích xuất AI</div>
                    </div>
                    {useGpu && <div className="w-2 h-2 rounded-full bg-[#B8E900]" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Batch Progress Bar during conversion */}
            {isProcessing && batchProgress && (
              <div className="p-4 rounded-xl bg-[#181A22] border border-[#B8E900]/50 space-y-3 shadow-lg">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2 text-white font-bold font-tech uppercase">
                    <Zap className="w-3.5 h-3.5 text-[#B8E900] animate-pulse" />
                    <span>
                      Đang bóc tách OCR {Math.min(batchProgress.total, batchProgress.current + 1)} / {batchProgress.total} ({batchProgress.percent}%)
                    </span>
                  </div>
                  <div className="flex items-center gap-2.5 text-[11px] font-mono">
                    <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#222530] border border-[#2E313E] text-[#B8E900] font-bold">
                      <Timer className="w-3.5 h-3.5 text-[#B8E900]" />
                      <span>{String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')}:{String(elapsedSeconds % 60).padStart(2, '0')}</span>
                    </div>
                    <span className="text-white font-bold">
                      {batchProgress.successCount} hoàn thành
                    </span>
                    {batchProgress.failedCount > 0 && (
                      <span className="text-[#FF3355] font-bold">
                        • {batchProgress.failedCount} lỗi
                      </span>
                    )}
                  </div>
                </div>

                <div className="w-full h-2 bg-[#222530] rounded-full overflow-hidden border border-[#2E313E]">
                  <div
                    className="h-full bg-[#B8E900] transition-all duration-300 shadow-[0_0_10px_rgba(184,233,0,0.6)]"
                    style={{
                      width: `${Math.max(5, Math.min(100, batchProgress.percent))}%`,
                    }}
                  />
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF]">
                  <p className="truncate">
                    📄 <span className="text-white font-semibold">{batchProgress.currentFilename}</span>
                  </p>
                  <span className="text-[#B8E900] font-bold ml-2 flex-shrink-0">
                    {batchProgress.stageText}
                  </span>
                </div>
              </div>
            )}

            {/* Batch Results Summary Card */}
            {batchResults && batchResults.length > 0 && (
              <div className="p-4 sm:p-5 rounded-xl bg-[#181A22] border border-[#2E313E] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#282B37]">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-5 h-5 text-[#B8E900]" />
                    <div>
                      <h5 className="text-xs font-bold font-tech uppercase tracking-wider text-white">
                        KẾT QUẢ BÓC TÁCH OCR HÀNG LOẠT
                      </h5>
                      <p className="text-[11px] font-mono text-[#9CA3AF]">
                        {batchResults.filter((r) => r.status === 'completed').length} /{' '}
                        {batchResults.length} tệp tin hoàn thành
                        {finalDuration !== null && (
                          <span className="ml-2 text-white font-bold">
                            • Thời gian: {String(Math.floor(finalDuration / 60)).padStart(2, '0')}:{String(finalDuration % 60).padStart(2, '0')}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleDownloadAll}
                      className="text-xs h-8 px-3"
                    >
                      <Download className="w-3.5 h-3.5 mr-1" />
                      Tải Về Tất Cả ({batchResults.filter((r) => r.status === 'completed').length})
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleClear}
                      className="text-xs h-8 px-3 text-[#9CA3AF] hover:text-white"
                    >
                      Bóc Tách Đợt Mới
                    </Button>
                  </div>
                </div>

                <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
                  {batchResults.map((res, i) => (
                    <div
                      key={i}
                      className="flex flex-col sm:flex-row sm:items-center justify-between p-2.5 rounded-xl bg-[#222530] border border-[#2E313E] text-xs font-mono gap-2"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {res.status === 'completed' ? (
                          <CheckCircle2 className="w-4 h-4 text-[#B8E900] flex-shrink-0" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-[#FF3355] flex-shrink-0" />
                        )}
                        <span className="text-white truncate font-semibold">{res.file.name}</span>
                        <span className="text-[#6B7280]">➔</span>
                        <span className="text-[#B8E900] font-bold uppercase">{outputFormat}</span>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-auto">
                        {res.status === 'completed' && res.job ? (
                          <span className="text-[#B8E900] font-bold text-[11px]">Hoàn thành</span>
                        ) : (
                          <span className="text-[#FF3355] text-[11px]">{res.error || 'Lỗi xử lý'}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action Button */}
            {batchResults && batchResults.length > 0 ? (
              <div className="pt-2 space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={handleDownloadAll}
                    className="py-3.5 text-sm font-black"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    TẢI VỀ TẤT CẢ ({batchResults.filter((r) => r.status === 'completed').length} TỆP)
                  </Button>

                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={handleClear}
                    className="py-3.5 text-sm font-bold"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    BẮT ĐẦU ĐỢT OCR MỚI
                  </Button>
                </div>
              </div>
            ) : (
              <div className="pt-2">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={handleRunOcr}
                  isLoading={isProcessing}
                  className="w-full py-3.5 sm:py-4 text-sm font-black"
                >
                  <Zap className="w-4 h-4 mr-1.5" />
                  {isProcessing
                    ? `ĐANG TRÍCH XUẤT OCR (${selectedFiles.length} TỆP)...`
                    : `TIẾN HÀNH BÓC TÁCH OCR TẤT CẢ (${selectedFiles.length} TỆP)`}
                </Button>
                <p className="text-center text-[11px] font-mono text-[#6B7280] mt-2.5">
                  Nhận diện và bảo toàn bố cục văn bản, bảng biểu phức tạp với PaddleOCR PP-Structure
                </p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}
