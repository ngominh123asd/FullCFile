import { useState, useEffect } from 'react'
import { AnimatePresence } from 'framer-motion'
import {
  FileText,
  Image as ImageIcon,
  Table as TableIcon,
  Zap,
  Download,
  Eye,
  FileType2,
  RefreshCw,
  Layers,
  Trash2,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  X,
  Plus,
  CheckCircle2,
  ArrowRight,
  Cpu,
  Radio,
  Sliders,
} from 'lucide-react'
import { Button } from '../components/ui/button'
import DropZone from '../components/ui/dropzone'
import DocumentPreview from '../components/ui/DocumentPreview'
import PageSizeDropdown from '../components/ui/PageSizeDropdown'
import OcrStudio from '../components/features/OcrStudio'
import SpreadsheetStudio from '../components/features/SpreadsheetStudio'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { filesApi, convertApi, jobsApi } from '../lib/api'
import { Job, UploadedFile } from '../types'
import { formatDate, formatBytes, getFormatIconBadge, formatJobDuration } from '../lib/utils'
import toast from 'react-hot-toast'
import { useI18n } from '../lib/i18n'
import { useTransferStore } from '../lib/transferStore'

export interface StagedFile extends UploadedFile {
  targetFormat: string
}

export default function DashboardPage() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const {
    uploadedFile: transferUploadedFile,
    uploadedFiles: transferUploadedFiles,
    pendingFiles: transferPendingFiles,
    clear: clearTransfer,
  } = useTransferStore()

  const [activeStudioTab, setActiveStudioTab] = useState<'universal' | 'ocr' | 'spreadsheet'>('universal')
  const [selectedFiles, setSelectedFiles] = useState<StagedFile[]>([])
  const [outputFormat, setOutputFormat] = useState<string>('docx')
  const [isConverting, setIsConverting] = useState(false)
  const [previewJobId, setPreviewJobId] = useState<string | null>(null)
  const [isClearingAll, setIsClearingAll] = useState(false)
  const [confirmClearAll, setConfirmClearAll] = useState(false)

  // Batch conversion progress & results states
  const [batchProgress, setBatchProgress] = useState<{
    total: number
    current: number
    currentFilename: string
    successCount: number
    failedCount: number
  } | null>(null)
  const [batchResults, setBatchResults] = useState<Array<{
    file: StagedFile
    job?: Job
    error?: string
    status: 'completed' | 'failed'
  }> | null>(null)

  // History search, filter, and pagination states
  const [historySearch, setHistorySearch] = useState('')
  const [historyStatusFilter, setHistoryStatusFilter] = useState<'all' | 'completed' | 'processing' | 'failed'>('all')
  const [historyTypeFilter, setHistoryTypeFilter] = useState<'all' | 'convert' | 'ocr' | 'spreadsheet'>('all')
  const [historyPage, setHistoryPage] = useState(1)
  const [historyPageSize, setHistoryPageSize] = useState(5)

  // Reset to page 1 whenever filters change
  useEffect(() => {
    setHistoryPage(1)
  }, [historySearch, historyStatusFilter, historyTypeFilter, historyPageSize])

  const normalizeInputFormat = (filename?: string) => {
    if (!filename) return ''
    const raw = filename.split('.').pop()?.toLowerCase() || ''
    if (raw === 'markdown' || raw === 'md') return 'md'
    if (raw === 'docx') return 'docx'
    if (raw === 'doc') return 'doc'
    if (raw === 'htm' || raw === 'html') return 'html'
    if (raw === 'txt' || raw === 'text') return 'txt'
    if (raw === 'pdf') return 'pdf'
    return raw
  }

  const allDocFormats = [
    { id: 'docx', label: 'DOCX', desc: 'Microsoft Word' },
    { id: 'pdf', label: 'PDF', desc: 'Vector Render' },
    { id: 'html', label: 'HTML', desc: 'Web Document' },
    { id: 'md', label: 'MARKDOWN', desc: 'GitHub Markdown' },
    { id: 'txt', label: 'TEXT', desc: 'Plain String' },
  ]

  const commonInputExt =
    selectedFiles.length > 0 &&
    selectedFiles.every(
      (f) => normalizeInputFormat(f.original_filename) === normalizeInputFormat(selectedFiles[0].original_filename)
    )
      ? normalizeInputFormat(selectedFiles[0].original_filename)
      : null

  const displayedDocFormats = allDocFormats.filter((fmt) => {
    if (!commonInputExt) return true
    return fmt.id !== commonInputExt
  })

  const getRecommendedOutputFormat = (filename?: string): string => {
    const ext = normalizeInputFormat(filename)
    if (ext === 'docx') return 'pdf'
    if (ext === 'doc') return 'docx'
    if (ext === 'pdf') return 'docx'
    if (ext === 'md') return 'docx'
    if (ext === 'html') return 'docx'
    if (ext === 'txt') return 'docx'
    return 'docx'
  }

  const removeFileFromQueue = (fileId: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.id !== fileId))
    if (batchResults) {
      setBatchResults((prev) => (prev ? prev.filter((r) => r.file.id !== fileId) : null))
    }
  }

  const applyGlobalTargetFormat = (format: string) => {
    setOutputFormat(format)
    setSelectedFiles((prev) =>
      prev.map((f) => {
        const ext = normalizeInputFormat(f.original_filename)
        return ext === format ? f : { ...f, targetFormat: format }
      })
    )
    setBatchResults(null)
  }

  // Listen to transfer store from Hero / Landing page drop
  useEffect(() => {
    if (transferUploadedFiles && transferUploadedFiles.length > 0) {
      const staged: StagedFile[] = transferUploadedFiles.map((f) => ({
        ...f,
        targetFormat: getRecommendedOutputFormat(f.original_filename),
      }))
      setSelectedFiles(staged)
      setBatchResults(null)

      const firstExt = normalizeInputFormat(staged[0].original_filename)
      if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'].includes(firstExt)) {
        setActiveStudioTab('ocr')
      } else if (['xlsx', 'xls', 'csv', 'tsv'].includes(firstExt)) {
        setActiveStudioTab('spreadsheet')
      } else {
        setActiveStudioTab('universal')
        setOutputFormat(staged[0].targetFormat)
      }
      clearTransfer()
    } else if (transferUploadedFile) {
      const staged: StagedFile = {
        ...transferUploadedFile,
        targetFormat: getRecommendedOutputFormat(transferUploadedFile.original_filename),
      }
      setSelectedFiles([staged])
      setBatchResults(null)

      const ext = normalizeInputFormat(transferUploadedFile.original_filename)
      if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'].includes(ext)) {
        setActiveStudioTab('ocr')
      } else if (['xlsx', 'xls', 'csv', 'tsv'].includes(ext)) {
        setActiveStudioTab('spreadsheet')
      } else {
        setActiveStudioTab('universal')
        setOutputFormat(staged.targetFormat)
      }
      clearTransfer()
    } else if (transferPendingFiles && transferPendingFiles.length > 0) {
      handleFilesSelected(transferPendingFiles)
      clearTransfer()
    }
  }, [transferUploadedFile, transferUploadedFiles, transferPendingFiles])

  // Fetch recent jobs
  const { data: recentJobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ['jobs', 'recent'],
    queryFn: async () => {
      const res = await jobsApi.list()
      return res.data
    },
    refetchInterval: 4000,
  })

  // Filter and paginate history jobs
  const filteredRecentJobs = (recentJobs || []).filter((job: Job) => {
    const q = historySearch.toLowerCase().trim()
    const matchesSearch =
      !q ||
      job.id.toLowerCase().includes(q) ||
      job.output_format.toLowerCase().includes(q) ||
      (job.input_filename && job.input_filename.toLowerCase().includes(q))

    const matchesStatus =
      historyStatusFilter === 'all' ||
      (historyStatusFilter === 'completed' && job.status === 'completed') ||
      (historyStatusFilter === 'processing' && (job.status === 'processing' || job.status === 'pending')) ||
      (historyStatusFilter === 'failed' && job.status === 'failed')

    const matchesType = historyTypeFilter === 'all' || job.job_type === historyTypeFilter

    return matchesSearch && matchesStatus && matchesType
  })

  const totalHistoryItems = filteredRecentJobs.length
  const totalHistoryPages = Math.max(1, Math.ceil(totalHistoryItems / historyPageSize))
  const currentHistoryPage = Math.min(historyPage, totalHistoryPages)
  const startIdx = (currentHistoryPage - 1) * historyPageSize
  const paginatedRecentJobs = filteredRecentJobs.slice(startIdx, startIdx + historyPageSize)

  const handleFilesSelected = async (files: File[]) => {
    setIsConverting(true)
    try {
      const res = await filesApi.upload(files)
      const newUploaded: StagedFile[] = res.data.files.map((f) => ({
        ...f,
        targetFormat: getRecommendedOutputFormat(f.original_filename),
      }))

      setSelectedFiles((prev) => {
        const existingIds = new Set(prev.map((p) => p.id))
        const filtered = newUploaded.filter((n) => !existingIds.has(n.id))
        return [...prev, ...filtered]
      })

      if (newUploaded.length > 0) {
        setOutputFormat(newUploaded[0].targetFormat)
      }

      setBatchResults(null)
      toast.success(
        newUploaded.length === 1
          ? `Đã nạp tệp: ${newUploaded[0].original_filename}`
          : `Đã nạp thành công ${newUploaded.length} tệp tin!`
      )
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Tải lên thất bại'
      toast.error(errorMsg)
    } finally {
      setIsConverting(false)
    }
  }

  const handleUniversalConvert = async () => {
    if (selectedFiles.length === 0) {
      toast.error('Vui lòng chọn hoặc kéo thả các tệp tin cần chuyển đổi')
      return
    }

    setIsConverting(true)
    setBatchProgress({
      total: selectedFiles.length,
      current: 0,
      currentFilename: selectedFiles[0].original_filename,
      successCount: 0,
      failedCount: 0,
    })
    setBatchResults([])

    const results: Array<{
      file: StagedFile
      job?: Job
      error?: string
      status: 'completed' | 'failed'
    }> = []

    let lastCompletedJobId: string | null = null

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i]
      const targetFmt = file.targetFormat || outputFormat

      setBatchProgress({
        total: selectedFiles.length,
        current: i + 1,
        currentFilename: file.original_filename,
        successCount: results.filter((r) => r.status === 'completed').length,
        failedCount: results.filter((r) => r.status === 'failed').length,
      })

      try {
        const res = await convertApi.convert({
          input_file_id: file.id,
          output_format: targetFmt,
          options: {
            toc: true,
            page_numbers: true,
          },
        })

        const job = res.data
        if (job.status === 'completed') {
          results.push({ file, job, status: 'completed' })
          lastCompletedJobId = job.id

          if (localStorage.getItem('fileforge_auto_download') === 'true') {
            handleDownload(job.id)
          }
        } else {
          results.push({ file, job, error: job.error || 'Lỗi xử lý', status: 'failed' })
        }
      } catch (err: any) {
        results.push({
          file,
          error: err.response?.data?.detail || err.message || 'Chuyển đổi thất bại',
          status: 'failed',
        })
      }
    }

    const successCount = results.filter((r) => r.status === 'completed').length
    const failedCount = results.filter((r) => r.status === 'failed').length

    setBatchResults(results)
    setIsConverting(false)
    setBatchProgress(null)
    queryClient.invalidateQueries({ queryKey: ['jobs'] })

    if (successCount === selectedFiles.length) {
      toast.success(`Đã xử lý thành công tất cả ${successCount} tệp!`)
    } else if (successCount > 0) {
      toast.success(`Hoàn tất: ${successCount} thành công, ${failedCount} thất bại`)
    } else {
      toast.error(`Xử lý thất bại cho toàn bộ ${failedCount} tệp`)
    }

    if (selectedFiles.length === 1 && lastCompletedJobId) {
      setPreviewJobId(lastCompletedJobId)
    }

    if (successCount > 0) {
      setSelectedFiles([])
      clearTransfer()
    }
  }

  const handleDownloadAllCompleted = async () => {
    if (!batchResults) return
    const completed = batchResults.filter((r) => r.status === 'completed' && r.job)
    if (completed.length === 0) {
      toast.error('Không có tệp nào hoàn thành để tải về')
      return
    }

    toast.success(`Bắt đầu tải về ${completed.length} tệp tin...`)
    for (let i = 0; i < completed.length; i++) {
      const item = completed[i]
      if (item.job) {
        await handleDownload(item.job.id)
        await new Promise((resolve) => setTimeout(resolve, 350))
      }
    }
  }

  const handleDownload = async (jobId: string) => {
    try {
      const res = await jobsApi.download(jobId)
      let filename = ''
      const disposition = res.headers?.['content-disposition'] || ''
      if (disposition && disposition.indexOf('filename=') !== -1) {
        const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition)
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '').trim()
        }
      }

      if (!filename) {
        const job = recentJobs?.find((j: any) => j.id === jobId)
        const ext = job?.output_format || 'pdf'
        const baseName = job?.input_filename
          ? job.input_filename.replace(/\.[^/.]+$/, '')
          : `fileforge_${jobId.slice(0, 8)}`
        filename = `${baseName}.${ext}`
      }

      const contentType = typeof res.headers?.['content-type'] === 'string'
        ? res.headers['content-type']
        : 'application/octet-stream'

      const blob = new Blob([res.data], { type: contentType })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      toast.success(`Đã tải xuống: ${filename}`)
    } catch (err: any) {
      toast.error(`Tải xuống thất bại: ${err.message}`)
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    try {
      await jobsApi.delete(jobId)
      toast.success('Đã xóa tác vụ khỏi nhật ký')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } catch (err: any) {
      toast.error(`Xóa thất bại: ${err.message}`)
    }
  }

  const handleClearAllJobs = async () => {
    if (!confirmClearAll) {
      setConfirmClearAll(true)
      setTimeout(() => setConfirmClearAll(false), 4000)
      return
    }

    setIsClearingAll(true)
    setConfirmClearAll(false)
    try {
      await jobsApi.clearAll()
      toast.success('Đã dọn sạch toàn bộ nhật ký tác vụ!')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } catch (err: any) {
      toast.error(`Dọn dẹp thất bại: ${err.message}`)
    } finally {
      setIsClearingAll(false)
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8 min-w-0 max-w-full overflow-hidden">
      {/* 1. TOP STUDIO NAVIGATION: ZZZ Pill Capsule Bar (Screenshot 1 & 3) */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="zzz-pill-container">
          <button
            onClick={() => setActiveStudioTab('universal')}
            className={activeStudioTab === 'universal' ? 'zzz-pill-active' : 'zzz-pill-inactive'}
          >
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 inline" />
              <span>Chuyển Đổi</span>
            </span>
          </button>

          <button
            onClick={() => setActiveStudioTab('ocr')}
            className={activeStudioTab === 'ocr' ? 'zzz-pill-active' : 'zzz-pill-inactive'}
          >
            <span className="flex items-center gap-1.5">
              <ImageIcon className="w-3.5 h-3.5 inline" />
              <span>Trích Xuất OCR</span>
            </span>
          </button>

          <button
            onClick={() => setActiveStudioTab('spreadsheet')}
            className={activeStudioTab === 'spreadsheet' ? 'zzz-pill-active' : 'zzz-pill-inactive'}
          >
            <span className="flex items-center gap-1.5">
              <TableIcon className="w-3.5 h-3.5 inline" />
              <span>Bảng Tính Matrix</span>
            </span>
          </button>
        </div>

        <div className="text-xs font-mono text-[#9CA3AF] hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-[#181A22] border border-[#282B37]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
          <span>FUNCTIONS // AST ENGINE ONLINE</span>
        </div>
      </div>

      {/* 2. ACTIVE STUDIO WORKSTATION CONTENT */}
      <div>
        {activeStudioTab === 'universal' && (
          <div className="space-y-6">
            {selectedFiles.length === 0 ? (
              /* When no files are staged: Dropzone + Functions Style Spec Deck */
              <div className="space-y-6">
                <DropZone
                  onFilesSelected={handleFilesSelected}
                  isLoading={isConverting}
                  maxFiles={50}
                  helperText="Kéo thả hoặc chọn nhiều tài liệu cùng lúc: Word (.docx, .doc), Markdown (.md), PDF (.pdf), HTML (.html), Text (.txt)"
                />

                {/* Sub Quick Spec Deck (Screenshot 1: tactile dark tiles) */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="p-4 rounded-2xl bg-[#181A22] border border-[#2A2D3A] flex items-center gap-3.5 shadow-sm">
                    <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] text-white font-black text-sm flex items-center justify-center flex-shrink-0">
                      01
                    </div>
                    <div>
                      <p className="font-tech font-bold text-xs uppercase text-white">CHUẨN ĐỊNH DẠNG AST</p>
                      <p className="text-[11px] font-mono text-[#9CA3AF]">Giữ nguyên cấu trúc, tiêu đề &amp; bảng biểu</p>
                    </div>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#181A22] border border-[#2A2D3A] flex items-center gap-3.5 shadow-sm">
                    <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] text-white font-black text-sm flex items-center justify-center flex-shrink-0">
                      02
                    </div>
                    <div>
                      <p className="font-tech font-bold text-xs uppercase text-white">XỬ LÝ ĐỒNG THỜI</p>
                      <p className="text-[11px] font-mono text-[#9CA3AF]">Chuyển đổi tối đa 50 tệp với 1 chạm</p>
                    </div>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#181A22] border border-[#2A2D3A] flex items-center gap-3.5 shadow-sm">
                    <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] text-white font-black text-sm flex items-center justify-center flex-shrink-0">
                      03
                    </div>
                    <div>
                      <p className="font-tech font-bold text-xs uppercase text-white">AN TOÀN BẢO MẬT</p>
                      <p className="text-[11px] font-mono text-[#9CA3AF]">Xóa sạch dữ liệu sau khi tải về thành công</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* When files are staged: 2-COLUMN HARDWARE SPLIT (Screenshot 1 & 3) */
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* LEFT COLUMN (7 cols, ~60%): Staging Bay + Format Pushbuttons + Primary Button */}
                <div className="lg:col-span-7 space-y-5">
                  <div className="zzz-device-frame p-5 sm:p-6 space-y-5">
                    {/* Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#282B37]">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white flex-shrink-0">
                          <FileType2 className="w-5 h-5 stroke-[2]" />
                        </div>
                        <div>
                          <h4 className="text-sm sm:text-base font-bold font-tech uppercase tracking-wider text-white">
                            HÀNG ĐỢI XỬ LÝ ({selectedFiles.length} TỆP)
                          </h4>
                          <p className="text-xs font-mono text-[#9CA3AF]">
                            TỔNG DUNG LƯỢNG: {formatBytes(selectedFiles.reduce((acc, f) => acc + (f.file_size || 0), 0))}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <label className="cursor-pointer btn-zzz-dark flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase transition-all">
                          <Plus className="w-3.5 h-3.5 text-white" />
                          <span>[+ THÊM TỆP]</span>
                          <input
                            type="file"
                            accept=".docx,.doc,.md,.html,.htm,.pdf,.txt"
                            multiple
                            className="hidden"
                            onChange={(e) => {
                              if (e.target.files && e.target.files.length > 0) {
                                handleFilesSelected(Array.from(e.target.files))
                              }
                            }}
                          />
                        </label>
                        <button
                          onClick={() => {
                            setSelectedFiles([])
                            setBatchResults(null)
                          }}
                          className="px-3 py-1.5 rounded-xl bg-[#221418] border border-[#FF3355]/40 text-[#FF3355] text-xs font-tech font-bold uppercase hover:bg-[#FF3355] hover:text-white transition-colors"
                        >
                          XÓA TẤT CẢ
                        </button>
                      </div>
                    </div>

                    {/* Staged Files List (Screenshot 1: Tiles) */}
                    <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1 custom-scrollbar">
                      {selectedFiles.map((file, idx) => {
                        const ext = normalizeInputFormat(file.original_filename)
                        const currentTarget = file.targetFormat || outputFormat
                        const targetLabel =
                          allDocFormats.find((f) => f.id === currentTarget)?.label || currentTarget.toUpperCase()

                        return (
                          <div
                            key={file.id || idx}
                            className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl bg-[#222530] border border-[#2E313E] hover:border-[#4A5064] transition-all gap-2.5"
                          >
                            <div className="flex items-center gap-2.5 min-w-0 flex-1">
                              <span className="w-7 h-6 rounded-lg bg-[#181A22] border border-[#2E313E] flex items-center justify-center text-[10px] font-mono font-bold text-white flex-shrink-0">
                                #{idx + 1}
                              </span>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-tech font-bold text-white truncate" title={file.original_filename}>
                                  {file.original_filename}
                                </p>
                                <p className="text-[10px] font-mono text-[#9CA3AF]">
                                  {formatBytes(file.file_size)} • {file.file_type.toUpperCase()}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-center gap-2.5 flex-shrink-0 self-end sm:self-auto">
                              <div className="flex items-center gap-1.5 text-xs font-mono">
                                <span className="px-2 py-0.5 rounded-md bg-[#181A22] text-[#9CA3AF] border border-[#2E313E] uppercase font-bold text-[10px]">
                                  [{ext}]
                                </span>
                                <ArrowRight className="w-3.5 h-3.5 text-white" />
                                <span className="px-2.5 py-0.5 rounded-md bg-[#B8E900] text-[#0C0D10] font-tech font-black text-xs uppercase shadow-sm">
                                  [{targetLabel}]
                                </span>
                              </div>

                              <button
                                onClick={() => removeFileFromQueue(file.id)}
                                title="Bỏ chọn tệp"
                                className="p-1 rounded-md bg-[#181A22] border border-[#2E313E] text-[#FF3355] hover:bg-[#FF3355] hover:text-white text-[10px] font-mono transition-all"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    {/* Target Format Pushbuttons (Screenshot 1: Tiles) */}
                    <div className="p-4 rounded-xl bg-[#14151C] border border-[#282B37] space-y-3">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-tech font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                          <Sliders className="w-3.5 h-3.5 text-[#B8E900]" />
                          <span>CHỌN ĐỊNH DẠNG ĐÍCH CHUNG:</span>
                        </label>
                        <span className="text-[11px] font-mono font-bold text-white px-2 py-0.5 rounded-full bg-[#222530] border border-[#2E313E]">
                          ACTIVE: [{outputFormat.toUpperCase()}]
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {displayedDocFormats.map((fmt) => {
                          const isSelected = outputFormat === fmt.id
                          return (
                            <button
                              key={fmt.id}
                              type="button"
                              onClick={() => applyGlobalTargetFormat(fmt.id)}
                              className={`p-2.5 rounded-xl border text-left transition-all ${
                                isSelected
                                  ? 'bg-[#B8E900] text-[#0C0D10] border-[#B8E900] shadow-sm'
                                  : 'bg-[#222530] text-[#9CA3AF] border-[#2E313E] hover:text-white hover:bg-[#282B37]'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className={`text-xs font-tech font-bold uppercase tracking-wider ${isSelected ? 'text-[#0C0D10]' : 'text-white'}`}>
                                  [{fmt.label}]
                                </span>
                                {isSelected && <span className="w-2 h-2 rounded-full bg-[#0C0D10]" />}
                              </div>
                              <p className={`text-[10px] font-mono mt-0.5 truncate ${isSelected ? 'text-[#0C0D10]/80' : 'text-[#6B7280]'}`}>
                                {fmt.desc}
                              </p>
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    {/* Execute Primary CTA Button */}
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={handleUniversalConvert}
                        disabled={isConverting}
                        className="btn-zzz-primary w-full py-4 text-sm font-tech font-black uppercase tracking-wider flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                      >
                        <Zap className="w-4 h-4 fill-[#0C0D10] stroke-[#0C0D10]" />
                        {isConverting
                          ? `[ ĐANG THỰC HIỆN CHUYỂN ĐỔI: ${selectedFiles.length} TỆP... ]`
                          : `[ TIẾN HÀNH XỬ LÝ CHUYỂN ĐỔI // ${selectedFiles.length} TỆP ▶ ]`}
                      </button>
                    </div>
                  </div>
                </div>

                {/* RIGHT COLUMN (5 cols, ~40%): Telemetry Panel & Results Tray (Screenshot 1 & 3) */}
                <div className="lg:col-span-5 space-y-5">
                  {/* Telemetry Hardware Device Card */}
                  <div className="zzz-device-frame p-5 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between pb-3 border-b border-[#282B37]">
                      <div className="flex items-center gap-2">
                        <Radio className="w-4 h-4 text-[#B8E900]" />
                        <span className="font-tech font-bold text-xs uppercase tracking-wider text-white">
                          THÔNG SỐ PHẦN CỨNG // HUD
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-[#222530] text-white font-mono text-[10px] font-bold border border-[#2E313E]">
                        DEVICE .01
                      </span>
                    </div>

                    {/* Stats Table (Exact Layout of Screenshot 3) */}
                    <div className="p-3.5 rounded-xl bg-[#14151C] border border-[#282B37] space-y-2 text-xs font-mono">
                      <div className="flex items-center justify-between py-1 border-b border-[#20222C]">
                        <span className="text-[#9CA3AF]">NĂNG LƯỢNG HOA TIÊU</span>
                        <span className="text-white font-bold flex items-center gap-1">
                          <Zap className="w-3.5 h-3.5 text-[#B8E900] fill-[#B8E900]" /> 240 / 240 MAX
                        </span>
                      </div>
                      <div className="flex items-center justify-between py-1 border-b border-[#20222C]">
                        <span className="text-[#9CA3AF]">BỘ BIÊN DỊCH AST</span>
                        <span className="text-[#B8E900] font-bold">PANDOC 3.1 &amp; LIBRE 7.6</span>
                      </div>
                      <div className="flex items-center justify-between py-1 border-b border-[#20222C]">
                        <span className="text-[#9CA3AF]">ĐỘ CHUẨN ĐỊNH DẠNG</span>
                        <span className="text-white font-bold">99.8% ACADEMIC</span>
                      </div>
                      <div className="flex items-center justify-between py-1">
                        <span className="text-[#9CA3AF]">TRẠNG THÁI TIẾN TRÌNH</span>
                        <span className="text-white font-bold">{isConverting ? 'RUNNING' : 'STANDBY'}</span>
                      </div>
                    </div>

                    {/* Real-time Conversion Progress */}
                    {isConverting && batchProgress && (
                      <div className="p-3.5 rounded-xl bg-[#14151C] border border-[#B8E900]/50 space-y-2.5">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-[#B8E900] font-bold">
                            TIẾN ĐỘ: {batchProgress.current} / {batchProgress.total}
                          </span>
                          <span className="text-white font-black">
                            {Math.round((batchProgress.current / batchProgress.total) * 100)}%
                          </span>
                        </div>
                        <div className="w-full h-2 bg-[#222530] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#B8E900] transition-all duration-300"
                            style={{
                              width: `${Math.max(5, (batchProgress.current / batchProgress.total) * 100)}%`,
                            }}
                          />
                        </div>
                        <p className="text-[10px] font-mono text-[#9CA3AF] truncate">
                          ĐANG XỬ LÝ: <span className="text-white font-bold">{batchProgress.currentFilename}</span>
                        </p>
                      </div>
                    )}

                    {/* Companion State */}
                    <div className="p-3 rounded-xl bg-[#14151C] border border-[#282B37] flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-[#222530] border border-[#323646] flex items-center justify-center text-white flex-shrink-0">
                        <Cpu className="w-4 h-4" />
                      </div>
                      <div className="text-[11px] font-mono">
                        <p className="text-white font-bold">BANGBOO ASSISTANT</p>
                        <p className="text-[#9CA3AF]">Sẵn sàng hỗ trợ kiểm tra cấu trúc tài liệu</p>
                      </div>
                    </div>
                  </div>

                  {/* Batch Results Tray (If Finished) */}
                  {batchResults && batchResults.length > 0 && (
                    <div className="zzz-device-frame p-5 rounded-2xl space-y-3.5">
                      <div className="flex items-center justify-between pb-2.5 border-b border-[#282B37]">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-[#B8E900]" />
                          <h5 className="text-xs font-bold font-tech uppercase text-white">
                            KẾT QUẢ ĐÃ CHUYỂN ĐỔI
                          </h5>
                        </div>
                        <span className="text-[10px] font-mono text-white font-bold">
                          {batchResults.filter((r) => r.status === 'completed').length} / {batchResults.length} THÀNH CÔNG
                        </span>
                      </div>

                      <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
                        {batchResults.map((res, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between p-2.5 rounded-xl bg-[#222530] border border-[#2E313E] text-xs font-mono gap-2"
                          >
                            <span className="text-white truncate font-medium flex-1">
                              {res.file.original_filename}
                            </span>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              {res.status === 'completed' && res.job ? (
                                <>
                                  <button
                                    onClick={() => setPreviewJobId(res.job!.id)}
                                    className="px-2.5 py-1 rounded-lg bg-[#181A22] text-white hover:border-white border border-[#323646] text-[10px] font-bold uppercase transition-colors"
                                  >
                                    Xem
                                  </button>
                                  <button
                                    onClick={() => handleDownload(res.job!.id)}
                                    className="px-2.5 py-1 rounded-lg bg-[#B8E900] text-[#0C0D10] text-[10px] font-black uppercase transition-colors"
                                  >
                                    Tải
                                  </button>
                                </>
                              ) : (
                                <span className="text-[#FF3355] text-[10px] font-bold">LỖI</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="pt-2 flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={handleDownloadAllCompleted}
                          className="btn-zzz-primary py-2.5 text-xs font-tech font-bold uppercase tracking-wider flex items-center justify-center gap-2"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>TẢI VỀ TẤT CẢ KẾT QUẢ</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedFiles([])
                            setBatchResults(null)
                          }}
                          className="btn-zzz-dark py-2 text-xs font-tech font-bold uppercase text-[#9CA3AF] hover:text-white"
                        >
                          NẠP ĐỢT MỚI
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {activeStudioTab === 'ocr' && (
          <OcrStudio
            initialFiles={selectedFiles}
            onJobCreated={(job) => {
              setPreviewJobId(job.id)
              setSelectedFiles([])
              clearTransfer()
              queryClient.invalidateQueries({ queryKey: ['jobs'] })
            }}
          />
        )}

        {activeStudioTab === 'spreadsheet' && (
          <SpreadsheetStudio
            initialFiles={selectedFiles}
            onJobCreated={(job) => {
              setPreviewJobId(job.id)
              setSelectedFiles([])
              clearTransfer()
              queryClient.invalidateQueries({ queryKey: ['jobs'] })
            }}
          />
        )}
      </div>

      {/* 3. BOTTOM COMMISSION LOGS // HISTORY BOARD (Screenshot 3 Style) */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-4">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#282B37]">
          <div className="flex items-center gap-2.5">
            <h3 className="text-base font-bold font-tech uppercase tracking-wider text-white">
              NHẬT KÝ ỦY THÁC // COMMISSIONS
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold text-white bg-[#222530] border border-[#2E313E]">
              [{totalHistoryItems} / {recentJobs?.length || 0} TÁC VỤ]
            </span>
          </div>

          <div className="flex items-center gap-2">
            {recentJobs && recentJobs.length > 0 && (
              <button
                type="button"
                onClick={handleClearAllJobs}
                disabled={isClearingAll}
                className={`text-xs h-8 px-3 rounded-xl transition-all font-tech font-bold uppercase ${
                  confirmClearAll
                    ? 'bg-[#FF3355] text-white border border-[#FF3355]'
                    : 'bg-[#221418] text-[#FF3355] border border-[#FF3355]/40 hover:bg-[#FF3355] hover:text-white'
                }`}
              >
                <Trash2 className="w-3.5 h-3.5 inline mr-1" />
                {confirmClearAll ? '[XÁC NHẬN?]' : '[XÓA HẾT]'}
              </button>
            )}

            <button
              type="button"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['jobs'] })}
              className="btn-zzz-dark text-xs text-white h-8 px-3 flex items-center font-tech font-bold uppercase"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1 text-white" /> [LÀM MỚI]
            </button>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        {recentJobs && recentJobs.length > 0 && (
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 p-3 rounded-xl bg-[#14151C] border border-[#282B37]">
            {/* Search input */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
              <input
                type="text"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                placeholder="Tìm ủy thác theo tên file, định dạng, ID..."
                className="w-full h-8 pl-8 pr-7 text-xs rounded-xl bg-[#222530] border border-[#2E313E] text-white placeholder-[#6B7280] focus:outline-none focus:border-white transition-colors"
              />
              {historySearch && (
                <button
                  onClick={() => setHistorySearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-white p-0.5"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-2 max-w-full">
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 max-w-full custom-scrollbar">
                {/* Status Filter */}
                <div className="flex items-center gap-1 bg-[#222530] p-1 rounded-full border border-[#2E313E] text-[11px] flex-shrink-0">
                  {[
                    { id: 'all', label: 'Tất cả' },
                    { id: 'completed', label: 'Hoàn thành' },
                    { id: 'processing', label: 'Đang xử lý' },
                    { id: 'failed', label: 'Thất bại' },
                  ].map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setHistoryStatusFilter(s.id as any)}
                      className={`px-3 py-1 rounded-full text-xs transition-all font-tech font-bold uppercase whitespace-nowrap ${
                        historyStatusFilter === s.id
                          ? 'bg-[#B8E900] text-[#0C0D10]'
                          : 'text-[#9CA3AF] hover:text-white'
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>

                {/* Type Filter */}
                <div className="flex items-center gap-1 bg-[#222530] p-1 rounded-full border border-[#2E313E] text-[11px] flex-shrink-0">
                  {[
                    { id: 'all', label: 'Mọi loại' },
                    { id: 'convert', label: 'Tài liệu' },
                    { id: 'ocr', label: 'OCR' },
                    { id: 'spreadsheet', label: 'Bảng tính' },
                  ].map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setHistoryTypeFilter(t.id as any)}
                      className={`px-3 py-1 rounded-full text-xs transition-all font-tech font-bold uppercase whitespace-nowrap ${
                        historyTypeFilter === t.id
                          ? 'bg-white text-[#0C0D10]'
                          : 'text-[#9CA3AF] hover:text-white'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Page Size Dropdown */}
              <PageSizeDropdown
                value={historyPageSize}
                onChange={setHistoryPageSize}
                options={[5, 10, 20, 50]}
              />
            </div>
          </div>
        )}

        {/* Commission Rows List */}
        {isLoadingJobs ? (
          <div className="py-12 text-center text-xs font-mono text-[#6B7280]">
            Đang tải dữ liệu tác vụ...
          </div>
        ) : recentJobs && recentJobs.length > 0 ? (
          filteredRecentJobs.length > 0 ? (
            <div className="space-y-2.5">
              {paginatedRecentJobs.map((job: Job) => {
                const fmtBadge = getFormatIconBadge(job.output_format)
                return (
                  <div
                    key={job.id}
                    className="p-3 sm:p-3.5 rounded-xl bg-[#222530] border border-[#2E313E] hover:border-[#4A5064] transition-all space-y-2.5 min-w-0"
                  >
                    {/* Top row: Format Badge + File Title + Status Badge */}
                    <div className="flex items-start justify-between gap-2 min-w-0">
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <span
                          className={`px-2.5 py-0.5 rounded-lg text-[10px] sm:text-xs font-tech font-bold uppercase border flex-shrink-0 ${fmtBadge.bg} ${fmtBadge.text} ${fmtBadge.border}`}
                        >
                          [{fmtBadge.label}]
                        </span>

                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-tech font-bold uppercase text-white truncate" title={job.input_filename || job.id}>
                            {job.input_filename
                              ? job.input_filename
                              : job.job_type === 'ocr'
                              ? 'TRÍCH XUẤT OCR'
                              : job.job_type === 'spreadsheet'
                              ? 'MA TRẬN BẢNG TÍNH'
                              : 'TÀI LIỆU'}{' '}
                            <span className="text-[#9CA3AF]">➔ [{job.output_format.toUpperCase()}]</span>
                          </p>
                          <p className="text-[10px] font-mono text-[#6B7280] mt-0.5 truncate flex items-center gap-1.5">
                            <span>{formatDate(job.created_at)}</span>
                            {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds) && (
                              <span className="text-white bg-[#181A22] px-2 py-0.5 rounded-md font-semibold flex items-center gap-1">
                                ⏱ {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds)}
                              </span>
                            )}
                            <span>• ID: {job.id.slice(0, 12)}</span>
                          </p>
                        </div>
                      </div>

                      <div className="flex-shrink-0">
                        {/* NORMAL NOTIFICATION STATUS BADGE (NO RANKS) */}
                        <StatusBadge status={job.status} />
                      </div>
                    </div>

                    {/* Bottom row: Actions Toolbar */}
                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#2A2D3A]">
                      {job.status === 'completed' && (
                        <>
                          <button
                            type="button"
                            onClick={() => setPreviewJobId(job.id)}
                            className="btn-zzz-dark text-xs h-7 px-3 text-white flex items-center gap-1 font-tech font-bold uppercase"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            [XEM]
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownload(job.id)}
                            className="px-3 h-7 rounded-xl bg-white text-[#0C0D10] hover:bg-[#E5E7EB] flex items-center gap-1 font-tech font-bold uppercase transition-colors text-xs"
                          >
                            <Download className="w-3.5 h-3.5 stroke-[2.5]" />
                            [TẢI VỀ]
                          </button>
                        </>
                      )}

                      <button
                        type="button"
                        onClick={() => handleDeleteJob(job.id)}
                        title="Xóa tác vụ này"
                        className="h-7 w-7 rounded-xl bg-[#1C1E26] text-[#FF3355] hover:bg-[#FF3355] hover:text-white flex items-center justify-center transition-colors ml-auto sm:ml-0 border border-[#2E313E]"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="py-10 text-center space-y-3 bg-[#14151C] rounded-2xl border border-[#282B37]">
              <Search className="w-8 h-8 text-[#6B7280] mx-auto opacity-50" />
              <p className="text-xs text-[#9CA3AF]">Không tìm thấy tác vụ phù hợp với điều kiện tìm kiếm.</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setHistorySearch('')
                  setHistoryStatusFilter('all')
                  setHistoryTypeFilter('all')
                }}
                className="text-xs h-7 px-3 rounded-full"
              >
                Đặt lại bộ lọc
              </Button>
            </div>
          )
        ) : (
          <div className="py-12 text-center space-y-2">
            <FileText className="w-10 h-10 text-[#6B7280] mx-auto opacity-50" />
            <p className="text-sm text-[#9CA3AF]">{t('history.empty')}</p>
            <p className="text-xs text-[#6B7280]">{t('history.empty_sub')}</p>
          </div>
        )}

        {/* Pagination Footer */}
        {filteredRecentJobs.length > 0 && totalHistoryPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-[#282B37] text-xs">
            <div className="text-[#9CA3AF] font-mono text-[11px]">
              Hiển thị <span className="text-white font-semibold">{startIdx + 1}</span> -{' '}
              <span className="text-white font-semibold">
                {Math.min(startIdx + historyPageSize, totalHistoryItems)}
              </span>{' '}
              trong tổng số <span className="text-white font-semibold">{totalHistoryItems}</span> tác vụ
            </div>

            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setHistoryPage(1)}
                disabled={currentHistoryPage <= 1}
                title="Trang đầu"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronsLeft className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                disabled={currentHistoryPage <= 1}
                title="Trang trước"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>

              {/* Page Numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: totalHistoryPages }, (_, i) => i + 1)
                  .filter((p) => {
                    if (totalHistoryPages <= 5) return true
                    if (p === 1 || p === totalHistoryPages) return true
                    return Math.abs(p - currentHistoryPage) <= 1
                  })
                  .map((p, idx, arr) => {
                    const prev = arr[idx - 1]
                    const showEllipsis = prev && p - prev > 1
                    const isActive = p === currentHistoryPage

                    return (
                      <div key={p} className="flex items-center gap-1">
                        {showEllipsis && (
                          <span className="px-1 text-xs font-mono text-[#6B7280]">...</span>
                        )}
                        <button
                          onClick={() => setHistoryPage(p)}
                          className={`min-w-[28px] h-7 px-2 rounded-lg text-xs font-mono font-bold transition-all ${
                            isActive
                              ? 'bg-white text-[#0C0D10]'
                              : 'bg-[#222530] text-[#9CA3AF] hover:text-white'
                          }`}
                        >
                          {p}
                        </button>
                      </div>
                    )
                  })}
              </div>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => setHistoryPage((p) => Math.min(totalHistoryPages, p + 1))}
                disabled={currentHistoryPage >= totalHistoryPages}
                title="Trang sau"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setHistoryPage(totalHistoryPages)}
                disabled={currentHistoryPage >= totalHistoryPages}
                title="Trang cuối"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronsRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {previewJobId && (
          <DocumentPreview
            jobId={previewJobId}
            onClose={() => setPreviewJobId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}