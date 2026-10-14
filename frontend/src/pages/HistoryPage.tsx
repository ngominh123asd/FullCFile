import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../lib/api'
import { Job } from '../types'
import { StatusBadge } from '../components/ui/StatusBadge'
import { Button } from '../components/ui/button'
import DocumentPreview from '../components/ui/DocumentPreview'
import PageSizeDropdown from '../components/ui/PageSizeDropdown'
import { formatDate, getFormatIconBadge, formatJobDuration } from '../lib/utils'
import { AnimatePresence } from 'framer-motion'
import {
  Search,
  Download,
  Eye,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  X,
  RefreshCw,
} from 'lucide-react'
import toast from 'react-hot-toast'

export default function HistoryPage() {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'processing' | 'failed'>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | 'convert' | 'ocr' | 'spreadsheet'>('all')
  const [previewJobId, setPreviewJobId] = useState<string | null>(null)
  const [isClearingAll, setIsClearingAll] = useState(false)
  const [confirmClearAll, setConfirmClearAll] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Reset to page 1 whenever filters change
  useEffect(() => {
    setPage(1)
  }, [searchTerm, statusFilter, typeFilter, pageSize])

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs', 'all'],
    queryFn: async () => {
      const res = await jobsApi.list()
      return res.data
    },
    refetchInterval: 4000,
  })

  const filteredJobs = (jobs || []).filter((job: Job) => {
    const q = searchTerm.toLowerCase().trim()
    const matchesSearch =
      !q ||
      job.id.toLowerCase().includes(q) ||
      job.output_format.toLowerCase().includes(q) ||
      (job.input_filename && job.input_filename.toLowerCase().includes(q))

    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'completed' && job.status === 'completed') ||
      (statusFilter === 'processing' && (job.status === 'processing' || job.status === 'pending')) ||
      (statusFilter === 'failed' && job.status === 'failed')

    const matchesType = typeFilter === 'all' || job.job_type === typeFilter
    return matchesSearch && matchesStatus && matchesType
  })

  const totalItems = filteredJobs.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const currentPage = Math.min(page, totalPages)
  const startIdx = (currentPage - 1) * pageSize
  const paginatedJobs = filteredJobs.slice(startIdx, startIdx + pageSize)

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
        const job = (jobs || []).find((j: any) => j.id === jobId)
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

  const handleClearAll = async () => {
    if (!confirmClearAll) {
      setConfirmClearAll(true)
      setTimeout(() => setConfirmClearAll(false), 4000)
      return
    }

    setIsClearingAll(true)
    setConfirmClearAll(false)
    try {
      await jobsApi.clearAll()
      toast.success('Đã xóa toàn bộ nhật ký tác vụ!')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } catch (err: any) {
      toast.error(`Xóa toàn bộ thất bại: ${err.message}`)
    } finally {
      setIsClearingAll(false)
    }
  }

  const exportHistoryJson = () => {
    if (!jobs || jobs.length === 0) {
      toast.error('Không có dữ liệu tác vụ để xuất')
      return
    }
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(jobs, null, 2))
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute('href', dataStr)
    downloadAnchor.setAttribute('download', `zzz_commissions_${new Date().toISOString().slice(0, 10)}.json`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
    toast.success('Đã xuất toàn bộ nhật ký dạng JSON!')
  }

  return (
    <div className="space-y-4 sm:space-y-6 max-w-full min-w-0 overflow-hidden">
      {/* Header & Controls - ZZZ Device Frame (Screenshot 1 & 3) */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-4 max-w-full">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4 pb-3 border-b border-[#282B37]">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg sm:text-xl font-bold font-tech uppercase tracking-wider text-white truncate">
                NHẬT KÝ TÁC VỤ // COMMISSIONS
              </h2>
              <span className="px-3 py-0.5 rounded-full text-[10px] font-mono font-bold text-white bg-[#222530] border border-[#2E313E]">
                [{totalItems} / {jobs?.length || 0} TÁC VỤ]
              </span>
            </div>
            <p className="text-xs font-mono text-[#9CA3AF] mt-1">
              Theo dõi và tải lại toàn bộ các phiên chuyển đổi dữ liệu và OCR
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['jobs'] })}
              className="btn-zzz-dark text-xs h-8 sm:h-9 px-3 flex items-center font-tech font-bold uppercase"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1 text-white" /> [LÀM MỚI]
            </button>

            <button
              type="button"
              onClick={exportHistoryJson}
              className="px-3 h-8 sm:h-9 rounded-xl bg-white text-[#0C0D10] font-tech font-bold text-xs uppercase hover:bg-[#E5E7EB] transition-colors flex items-center"
            >
              <Download className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
              [XUẤT JSON]
            </button>

            {jobs && jobs.length > 0 && (
              <button
                type="button"
                onClick={handleClearAll}
                disabled={isClearingAll}
                className={`text-xs h-8 sm:h-9 px-3 rounded-xl transition-all font-tech font-bold uppercase ${
                  confirmClearAll
                    ? 'bg-[#FF3355] text-white border border-[#FF3355]'
                    : 'bg-[#221418] text-[#FF3355] border border-[#FF3355]/40 hover:bg-[#FF3355] hover:text-white'
                }`}
              >
                <Trash2 className="w-3.5 h-3.5 inline mr-1" />
                {confirmClearAll ? '[XÁC NHẬN?]' : '[XÓA TẤT CẢ]'}
              </button>
            )}
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-2.5 sm:gap-3 pt-2 max-w-full">
          {/* Search Box */}
          <div className="relative flex-1 min-w-0">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Tìm kiếm theo tên file, định dạng, ID..."
              className="w-full h-8 sm:h-9 pl-8 pr-7 text-xs rounded-xl bg-[#222530] border border-[#2E313E] text-white placeholder-[#6B7280] focus:outline-none focus:border-white transition-colors"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-white p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 max-w-full">
            {/* Status & Type Filter Pills Container */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 max-w-full custom-scrollbar">
              {/* Status Filter */}
              <div className="flex items-center gap-1 bg-[#222530] p-1 rounded-full border border-[#2E313E] text-xs flex-shrink-0">
                {[
                  { id: 'all', label: 'Tất cả' },
                  { id: 'completed', label: 'Hoàn thành' },
                  { id: 'processing', label: 'Đang xử lý' },
                  { id: 'failed', label: 'Thất bại' },
                ].map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setStatusFilter(s.id as any)}
                    className={`px-3 py-1 rounded-full text-xs transition-colors font-tech font-bold uppercase whitespace-nowrap ${
                      statusFilter === s.id
                        ? 'bg-[#B8E900] text-[#0C0D10]'
                        : 'text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              {/* Type Filter */}
              <div className="flex items-center gap-1 bg-[#222530] p-1 rounded-full border border-[#2E313E] text-xs flex-shrink-0">
                {[
                  { id: 'all', label: 'Tất cả loại' },
                  { id: 'convert', label: 'Tài liệu' },
                  { id: 'ocr', label: 'OCR' },
                  { id: 'spreadsheet', label: 'Bảng tính' },
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTypeFilter(t.id as any)}
                    className={`px-3 py-1 rounded-full text-xs transition-colors font-tech font-bold uppercase whitespace-nowrap ${
                      typeFilter === t.id
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
              value={pageSize}
              onChange={setPageSize}
              options={[5, 10, 20, 50]}
            />
          </div>
        </div>
      </div>

      {/* History Table Container */}
      <div className="zzz-device-frame overflow-hidden max-w-full min-w-0">
        {/* Desktop Table View */}
        <div className="hidden md:block overflow-x-auto custom-scrollbar">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-[#14151C] border-b border-[#282B37] text-[#9CA3AF] font-tech font-bold uppercase tracking-wider">
                <th className="p-3.5 pl-5">MÃ TÁC VỤ (JOB ID)</th>
                <th className="p-3.5">LOẠI ENGINE</th>
                <th className="p-3.5">ĐÍCH XUẤT</th>
                <th className="p-3.5">TRẠNG THÁI</th>
                <th className="p-3.5">THỜI GIAN KHỞI TẠO</th>
                <th className="p-3.5 pr-5 text-right">THAO TÁC</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-[#6B7280] font-mono">
                    [ĐANG TẢI DỮ LIỆU TÁC VỤ...]
                  </td>
                </tr>
              ) : paginatedJobs.length > 0 ? (
                paginatedJobs.map((job: Job) => {
                  const fmt = getFormatIconBadge(job.output_format)
                  return (
                    <tr
                      key={job.id}
                      className="border-b border-[#20222C] hover:bg-[#222530]/50 transition-colors font-mono"
                    >
                      <td className="p-3.5 pl-5">
                        <div className="font-tech font-bold uppercase text-white max-w-[260px] truncate" title={job.input_filename || job.id}>
                          {job.input_filename || job.id}
                        </div>
                        <div className="text-[10px] text-[#6B7280] font-mono">
                          ID: {job.id.slice(0, 12)}
                        </div>
                      </td>
                      <td className="p-3.5 text-[#9CA3AF] font-tech font-bold uppercase">
                        {job.job_type === 'ocr'
                          ? 'VISION OCR'
                          : job.job_type === 'spreadsheet'
                          ? 'SPREADSHEET MATRIX'
                          : 'DOC NORMALIZER'}
                      </td>
                      <td className="p-3.5">
                        <span
                          className={`px-2.5 py-0.5 rounded-lg text-[10px] font-tech font-bold uppercase border ${fmt.bg} ${fmt.text} ${fmt.border}`}
                        >
                          [{fmt.label}]
                        </span>
                      </td>
                      <td className="p-3.5">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="p-3.5 text-[#9CA3AF]">
                        <div>{formatDate(job.created_at)}</div>
                        {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds) && (
                          <div className="text-[10px] text-white font-semibold mt-0.5 flex items-center gap-1">
                            ⏱ {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds)}
                          </div>
                        )}
                      </td>
                      <td className="p-3.5 pr-5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {job.status === 'completed' && (
                            <>
                              <button
                                type="button"
                                onClick={() => setPreviewJobId(job.id)}
                                title="Xem trước kết quả"
                                className="btn-zzz-dark h-7 px-2.5 text-xs text-white flex items-center justify-center font-tech font-bold uppercase"
                              >
                                <Eye className="w-3.5 h-3.5 mr-1" />
                                Xem
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownload(job.id)}
                                title="Tải file kết quả"
                                className="h-7 px-3 rounded-xl bg-white text-[#0C0D10] hover:bg-[#E5E7EB] flex items-center justify-center text-xs font-tech font-bold uppercase transition-colors"
                              >
                                <Download className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
                                Tải
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeleteJob(job.id)}
                            title="Xóa tác vụ này"
                            className="h-7 w-7 rounded-xl bg-[#221418] text-[#FF3355] border border-[#FF3355]/40 hover:bg-[#FF3355] hover:text-white flex items-center justify-center transition-colors ml-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-[#6B7280] font-mono">
                    [KHÔNG TÌM THẤY DỮ LIỆU PHÙ HỢP]
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Dedicated Job Card List */}
        <div className="block md:hidden divide-y divide-[#20222C]">
          {isLoading ? (
            <div className="py-10 text-center text-[#6B7280] font-mono text-xs">
              Đang tải danh sách tác vụ...
            </div>
          ) : paginatedJobs.length > 0 ? (
            paginatedJobs.map((job: Job) => {
              const fmt = getFormatIconBadge(job.output_format)
              return (
                <div key={job.id} className="p-3.5 space-y-2.5 bg-[#181A22] hover:bg-[#1E202A] transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-bold text-xs text-white truncate font-tech uppercase" title={job.input_filename || job.id}>
                        {job.input_filename || job.id}
                      </div>
                      <div className="text-[10px] text-[#6B7280] font-mono mt-0.5">
                        ID: {job.id.slice(0, 12)}
                      </div>
                    </div>
                    <StatusBadge status={job.status} />
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono text-[#9CA3AF] pt-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] px-2 py-0.5 rounded-md bg-[#222530] text-[#9CA3AF] border border-[#2E313E]">
                        {job.job_type === 'ocr' ? 'OCR' : job.job_type === 'spreadsheet' ? 'Matrix' : 'Doc'}
                      </span>
                      <span className="text-[#6B7280]">➔</span>
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${fmt.bg} ${fmt.text} ${fmt.border}`}>
                        {fmt.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds) && (
                        <span className="text-white font-semibold">
                          ⏱ {formatJobDuration(job.started_at, job.completed_at, job.result?.duration_seconds)}
                        </span>
                      )}
                      <span className="text-[#9CA3AF]">{formatDate(job.created_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-1.5 pt-1 border-t border-[#20222C]">
                    {job.status === 'completed' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setPreviewJobId(job.id)}
                          className="btn-zzz-dark text-xs px-2.5 py-1 text-white font-tech font-bold uppercase"
                        >
                          <Eye className="w-3 h-3 inline mr-1" />
                          <span>Xem</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDownload(job.id)}
                          className="px-2.5 py-1 rounded-xl bg-white text-[#0C0D10] font-tech font-bold uppercase text-xs"
                        >
                          <Download className="w-3 h-3 inline mr-1 stroke-[2.5]" />
                          <span>Tải về</span>
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeleteJob(job.id)}
                      className="p-1 rounded-xl bg-[#221418] text-[#FF3355] border border-[#FF3355]/40 hover:bg-[#FF3355] hover:text-white transition-colors ml-auto"
                      title="Xóa"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )
            })
          ) : (
            <div className="py-10 text-center text-[#6B7280] font-mono text-xs">
              Không tìm thấy tác vụ phù hợp
            </div>
          )}
        </div>

        {/* Pagination Footer */}
        {filteredJobs.length > 0 && totalPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 bg-[#14151C] border-t border-[#282B37] text-xs">
            <div className="text-[#9CA3AF] font-mono text-[11px]">
              Hiển thị <span className="text-white font-semibold">{startIdx + 1}</span> -{' '}
              <span className="text-white font-semibold">
                {Math.min(startIdx + pageSize, totalItems)}
              </span>{' '}
              trong tổng số <span className="text-white font-semibold">{totalItems}</span> tác vụ
            </div>

            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage(1)}
                disabled={currentPage <= 1}
                title="Trang đầu"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronsLeft className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                title="Trang trước"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>

              {/* Page Numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter((p) => {
                    if (totalPages <= 5) return true
                    if (p === 1 || p === totalPages) return true
                    return Math.abs(p - currentPage) <= 1
                  })
                  .map((p, idx, arr) => {
                    const prev = arr[idx - 1]
                    const showEllipsis = prev && p - prev > 1
                    const isActive = p === currentPage

                    return (
                      <div key={p} className="flex items-center gap-1">
                        {showEllipsis && (
                          <span className="px-1 text-xs font-mono text-[#6B7280]">...</span>
                        )}
                        <button
                          onClick={() => setPage(p)}
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
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                title="Trang sau"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage(totalPages)}
                disabled={currentPage >= totalPages}
                title="Trang cuối"
                className="h-7 w-7 text-[#9CA3AF] disabled:opacity-30 hover:text-white"
              >
                <ChevronsRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Preview Modal */}
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
