import { useState, useEffect, useRef } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import {
  X,
  Download,
  Loader,
  FileText,
  Table as TableIcon,
  Share2,
  Copy,
  Check,
  Sparkles,
  ShieldCheck,
  Pencil,
  RotateCcw,
  Clock,
  AlertTriangle,
} from 'lucide-react'
import { Button } from './button'
import { jobsApi } from '../../lib/api'

interface DocumentPreviewProps {
  jobId: string
  onClose: () => void
}

function DocxPageSheet({ children, style, className }: {
  children: ReactNode; style: CSSProperties; className: string
}) {
  const container = useRef<HTMLDivElement>(null)
  const [available, setAvailable] = useState(0)
  useEffect(() => {
    const element = container.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setAvailable(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  const width = parseFloat(String(style.width)) * (String(style.width).endsWith('pt') ? 96 / 72 : 1)
  const zoom = available && width ? Math.min(1, available / width) : 1
  return <div ref={container} style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
    <div className={className} style={{ ...style, flexShrink: 0, zoom }}>{children}</div>
  </div>
}

interface PreviewBlock {
  type: 'paragraph' | 'table'
  style?: string
  content?: string
  font_name?: string
  font_size?: number
  align?: string
  data?: string[][]
}

interface PreviewData {
  job_id: string
  format: string
  previewable: boolean
  content?: string
  pages?: PreviewBlock[][]
  page_count?: number
  page_setups?: Array<{ width_pt: number; height_pt: number; top_pt: number; bottom_pt: number; left_pt: number; right_pt: number }>
  paragraphs?: Array<{ style: string; content: string; font_name?: string; align?: string }> | string[]
  tables?: unknown
  sheets?: Array<{ name: string; data: string[][]; cell_warnings?: Record<string, string> }>
  url?: string
  render_type?: string
  error?: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
}

function formatExecutionDuration(startedAt?: string, completedAt?: string, durationSeconds?: number): string {
  let seconds = durationSeconds
  if ((seconds === undefined || seconds === null) && startedAt && completedAt) {
    const diff = (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000
    if (diff > 0) seconds = Math.round(diff * 10) / 10
  }
  if (seconds === undefined || seconds === null || seconds <= 0) return ''
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`
  }
  const mins = Math.floor(seconds / 60)
  const remSecs = Math.round(seconds % 60)
  return `${mins}p ${remSecs}s`
}

function ScrollableMatrixViewer({
  title,
  rows,
  cellWarnings = {},
}: {
  title: string
  rows: any[][]
  cellWarnings?: Record<string, string>
}) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [colWidths, setColWidths] = useState<{ [key: number]: number }>({})

  const handleScrollLeft = () => {
    scrollContainerRef.current?.scrollBy({ left: -350, behavior: 'smooth' })
  }
  const handleScrollRight = () => {
    scrollContainerRef.current?.scrollBy({ left: 350, behavior: 'smooth' })
  }
  const handleScrollStart = () => {
    scrollContainerRef.current?.scrollTo({ left: 0, behavior: 'smooth' })
  }
  const handleScrollEnd = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        left: scrollContainerRef.current.scrollWidth,
        behavior: 'smooth',
      })
    }
  }

  const handleMouseDownResize = (colIndex: number, e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startWidth = colWidths[colIndex] || 130

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (moveEvent: MouseEvent) => {
      moveEvent.preventDefault()
      const diff = moveEvent.clientX - startX
      const newWidth = Math.max(40, Math.min(1200, startWidth + diff))
      setColWidths((prev) => ({
        ...prev,
        [colIndex]: newWidth,
      }))
    }

    const handleMouseUp = () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  const rowCount = rows ? rows.length : 0
  const colCount = rows && rows.length > 0
    ? Math.max(...rows.map((r: any) => (Array.isArray(r) ? r.length : 0)), 0)
    : 0

  return (
    <div className="rounded-xl bg-[#090A0F] border border-white/10 overflow-hidden shadow-lg space-y-0">
      {/* Sheet Title Bar & Navigation Controls */}
      <div className="px-4 py-3 bg-[#121622] border-b border-white/10 flex items-center justify-between flex-wrap gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <TableIcon className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold font-mono text-[#F0F6FC] flex items-center gap-2">
            <span>{title}</span>
          </h4>
        </div>

        {/* Horizontal Navigation Control Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-[#07090E] border border-white/10 rounded-lg p-0.5 text-xs font-mono">
            <button
              type="button"
              onClick={handleScrollStart}
              title="Về cột đầu tiên (Cột A)"
              className="px-2 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-white transition-colors"
            >
              ⏮
            </button>
            <button
              type="button"
              onClick={handleScrollLeft}
              title="Cuộn sang trái (-350px)"
              className="px-2.5 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-emerald-400 font-bold transition-colors flex items-center gap-1"
            >
              ❮ Trái
            </button>
            <div className="w-[1px] h-3.5 bg-white/10 my-auto mx-0.5" />
            <button
              type="button"
              onClick={handleScrollRight}
              title="Cuộn sang phải (+350px)"
              className="px-2.5 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-emerald-400 font-bold transition-colors flex items-center gap-1"
            >
              Phải ❯
            </button>
            <button
              type="button"
              onClick={handleScrollEnd}
              title="Đến cột cuối cùng"
              className="px-2 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-white transition-colors"
            >
              ⏭
            </button>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-mono text-[#94A3B8]">
            <span className="px-2.5 py-1 rounded-full bg-[#222530] border border-[#2E313E] text-white">
              {rowCount} hàng
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[#222530] border border-[#2E313E] text-[#B8E900]">
              {colCount} cột
            </span>
          </div>
        </div>
      </div>

      {/* Sub-bar hint */}
      <div className="px-3.5 py-1.5 bg-[#0C0F17] border-b border-white/5 flex items-center justify-between text-[11px] font-mono text-[#64748B]">
        <span>💡 Rê cạnh cột <code className="text-emerald-400 font-bold">|</code> để kéo chỉnh độ rộng • Giữ <kbd className="px-1 py-0.5 bg-white/10 text-[#CBD5E1] rounded text-[10px]">Shift</kbd> + Lăn chuột để cuộn ngang</span>
        <span className="text-[#94A3B8]">{rowCount} dòng</span>
      </div>

      {/* Scrollable Spreadsheet Table Container */}
      {Object.keys(cellWarnings).length > 0 && (
        <p className="px-3.5 py-2 text-xs text-amber-200 bg-amber-500/10">
          Ô màu vàng chứa chữ viết tay cần đối chiếu ảnh gốc. Rê chuột vào ô để xem ghi chú.
        </p>
      )}
      <div
        ref={scrollContainerRef}
        className="overflow-x-auto overflow-y-auto max-h-[440px] bg-white custom-scrollbar select-none"
      >
        <table className="border-collapse text-xs font-sans table-fixed" style={{ width: 'max-content' }}>
          <colgroup>
            <col style={{ width: '48px', minWidth: '48px', maxWidth: '48px' }} />
            {Array.from({ length: colCount }).map((_, ci) => {
              const width = colWidths[ci] || 130
              return (
                <col
                  key={ci}
                  style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                />
              )
            })}
          </colgroup>
          <thead className="bg-[#F1F5F9] sticky top-0 z-10 shadow-sm border-b-2 border-slate-300 select-none">
            {rowCount > 0 && (
              <tr>
                <th className="w-12 px-2.5 py-1.5 text-center text-[11px] font-mono font-bold text-slate-500 bg-[#E2E8F0] border-r border-slate-300 select-none sticky left-0 z-20">
                  #
                </th>
                {Array.from({ length: colCount }).map((_, ci) => {
                  let letter = ''
                  let temp = ci
                  while (temp >= 0) {
                    letter = String.fromCharCode((temp % 26) + 65) + letter
                    temp = Math.floor(temp / 26) - 1
                  }
                  const width = colWidths[ci] || 130
                  return (
                    <th
                      key={ci}
                      style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                      className="relative px-2.5 py-1.5 text-center text-xs font-mono font-bold text-slate-700 border-r border-slate-300 bg-[#F1F5F9] select-none group overflow-visible"
                    >
                      <span className="text-[11px] text-emerald-700 font-mono font-bold bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30">
                        [{letter}]
                      </span>
                      {/* Interactive Drag Handle for Column Width Resize */}
                      <div
                        onMouseDown={(e) => handleMouseDownResize(ci, e)}
                        title="Kéo sang trái/phải để chỉnh độ rộng cột"
                        className="absolute -right-2 top-0 bottom-0 w-4 cursor-col-resize hover:bg-emerald-500/80 active:bg-emerald-600 bg-transparent transition-colors z-40 flex items-center justify-center"
                      >
                        <div className="w-[1.5px] h-3.5 bg-slate-400/60 group-hover:bg-white" />
                      </div>
                    </th>
                  )
                })}
              </tr>
            )}
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {rows && rows.map((row: any, ri: number) => (
              <tr
                key={ri}
                className={ri % 2 === 0 ? 'bg-white hover:bg-emerald-50/70 transition-colors h-[28px]' : 'bg-slate-50/80 hover:bg-emerald-50/70 transition-colors h-[28px]'}
              >
                <td className="px-2.5 py-1 text-center text-[11px] font-mono font-bold text-slate-500 bg-slate-100/90 border-r border-slate-300 select-none sticky left-0 z-10">
                  {ri + 1}
                </td>
                {Array.from({ length: colCount }).map((_, ci) => {
                  const cell = Array.isArray(row) ? row[ci] : undefined
                  const width = colWidths[ci] || 130
                  return (
                    <td
                      key={ci}
                      style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px`, backgroundColor: cellWarnings[`${ri}:${ci}`] ? '#fff3cd' : undefined }}
                      className="px-2.5 py-1 text-slate-900 border-r border-slate-200 whitespace-nowrap text-xs font-normal truncate overflow-hidden"
                      title={cellWarnings[`${ri}:${ci}`] ? `${String(cell ?? '')} — ${cellWarnings[`${ri}:${ci}`]}` : String(cell ?? '')}
                    >
                      {String(cell ?? '') || '\u00A0'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function DocumentPreview({ jobId, onClose }: DocumentPreviewProps) {
  const [loading, setLoading] = useState(true)
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  const [copiedContent, setCopiedContent] = useState(false)
  const [copiedJobId, setCopiedJobId] = useState(false)
  const [customBaseName, setCustomBaseName] = useState(`fileforge_${jobId.slice(0, 8)}`)
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)

  useEffect(() => {
    loadPreview()
    setCustomBaseName(`fileforge_${jobId.slice(0, 8)}`)
  }, [jobId])

  const directDownloadUrl = new URL(`${(import.meta.env.VITE_API_URL || '/api/v1').replace(/\/+$/, '')}/jobs/${jobId}/download`, window.location.origin).href

  useEffect(() => {
    let active = true
    let blobUrlToRevoke: string | null = null

    if (preview?.format === 'pdf' && jobId) {
      setPdfLoading(true)
      jobsApi
        .download(jobId)
        .then((res) => {
          if (!active) return
          const blob =
            res.data instanceof Blob
              ? res.data
              : new Blob([res.data], { type: 'application/pdf' })
          const url = window.URL.createObjectURL(blob)
          blobUrlToRevoke = url
          setPdfBlobUrl(url)
        })
        .catch((err) => {
          console.error('Failed to load PDF preview blob:', err)
          if (active) setPdfBlobUrl(directDownloadUrl)
        })
        .finally(() => {
          if (active) setPdfLoading(false)
        })
    } else {
      setPdfBlobUrl(null)
    }

    return () => {
      active = false
      if (blobUrlToRevoke) {
        window.URL.revokeObjectURL(blobUrlToRevoke)
      }
    }
  }, [preview?.format, jobId, directDownloadUrl])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const loadPreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await jobsApi.preview(jobId)
      const data = response.data as PreviewData
      setPreview(data)
      if (data.error && !data.previewable) {
        setError(data.error)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load preview')
    } finally {
      setLoading(false)
    }
  }

  const renderDocxPages = () => {
    if (!preview) return null

    // 1. Structured pages from backend (in-order paragraphs & inline tables)
    if (preview.pages && Array.isArray(preview.pages) && preview.pages.length > 0) {
      return (
        <div className="flex flex-col items-center gap-3.5 w-full py-2">
          {preview.pages.map((pageBlocks: any[], pageIndex: number) => (
            <DocxPageSheet
              key={pageIndex}
              className="docx-page-sheet"
              style={{
                width: preview.page_setups?.[pageIndex] ? `${preview.page_setups[pageIndex].width_pt}pt` : '816px',
                minHeight: preview.page_setups?.[pageIndex] ? `${preview.page_setups[pageIndex].height_pt}pt` : '1056px',
                background: '#ffffff',
                boxShadow: '0 8px 25px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.1)',
                position: 'relative',
                boxSizing: 'border-box',
                padding: preview.page_setups?.[pageIndex]
                  ? `${preview.page_setups[pageIndex].top_pt}pt ${preview.page_setups[pageIndex].right_pt}pt ${preview.page_setups[pageIndex].bottom_pt}pt ${preview.page_setups[pageIndex].left_pt}pt`
                  : '64px 72px 64px 72px',
                borderRadius: '2px',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Main Content Flow */}
              <div className="docx-content flex-1">
                {pageBlocks.map((block: any, bi: number) => {
                  if (block.type === 'table' && block.data) {
                    const hasBorders = block.has_borders !== false
                    const colWidths = block.col_widths || []
                    const totalColWidth = colWidths.reduce((a: number, b: number) => a + b, 0)

                    return (
                      <table
                        key={bi}
                        className={`docx-table ${!hasBorders ? 'borderless-table' : ''}`}
                        style={{
                          width: totalColWidth > 0 ? `${totalColWidth}pt` : '100%',
                          maxWidth: '100%',
                          tableLayout: totalColWidth > 0 ? 'fixed' : 'auto',
                          margin: `0 0 0 ${block.indent_left_pt || 0}pt`,
                          borderCollapse: 'collapse',
                          border: hasBorders ? '1px solid #777777' : 'none',
                          boxSizing: 'border-box',
                        }}
                      >
                        {colWidths.length > 0 && totalColWidth > 0 && (
                          <colgroup>
                            {colWidths.map((w: number, ci: number) => (
                              <col key={ci} style={{ width: `${(w / totalColWidth) * 100}%` }} />
                            ))}
                          </colgroup>
                        )}
                        <tbody>
                          {block.data.map((row: string[], ri: number) => (
                            <tr key={ri} style={{ height: block.row_heights?.[ri] ? `${block.row_heights[ri]}pt` : undefined }}>
                              {row.map((cell: string, ci: number) => block.cell_props?.[ri]?.[ci]?.hidden ? null : (
                                <td
                                  key={ci}
                                  colSpan={block.cell_props?.[ri]?.[ci]?.colspan || 1}
                                  rowSpan={block.cell_props?.[ri]?.[ci]?.rowspan || 1}
                                  style={{
                                    border: hasBorders ? '1px solid #777777' : 'none',
                                    padding: block.cell_padding_pt && Object.keys(block.cell_padding_pt).length
                                      ? `${block.cell_padding_pt.top || 0}pt ${block.cell_padding_pt.right || 0}pt ${block.cell_padding_pt.bottom || 0}pt ${block.cell_padding_pt.left || 0}pt`
                                      : hasBorders ? (colWidths.length >= 8 ? '2pt 3pt' : '4pt 5pt') : '2pt 4pt',
                                    background: 'transparent',
                                    verticalAlign: 'top',
                                    overflowWrap: 'anywhere',
                                    wordBreak: 'break-word',
                                    boxSizing: 'border-box',
                                    color: '#000000',
                                  }}
                                  dangerouslySetInnerHTML={{ __html: cell || '' }}
                                />
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  }

                  const styleName = (block.style || 'Normal').toLowerCase()
                  let className = 'docx-para'
                  if (styleName.includes('heading 1') || styleName.includes('title')) {
                    className = 'docx-para docx-h1'
                  } else if (styleName.includes('heading 2')) {
                    className = 'docx-para docx-h2'
                  } else if (styleName.includes('heading 3')) {
                    className = 'docx-para docx-h3'
                  } else if (styleName.includes('heading 4')) {
                    className = 'docx-para docx-h4'
                  } else if (styleName.includes('heading')) {
                    className = 'docx-para docx-h5'
                  }

                  if (!block.content || !block.content.trim()) {
                    return <div key={bi} style={{ height: `${block.line_height_pt || block.font_size || 11}pt`,
                      marginTop: `${block.margin_top_pt || 0}pt`, marginBottom: `${block.margin_bottom_pt || 0}pt` }} />
                  }

                  return (
                    <div
                      key={bi}
                      className={className}
                      style={{
                        textAlign: (block.align as any) || 'left',
                        fontFamily: block.font_name ? `'${block.font_name}', 'Times New Roman', serif` : undefined,
                        fontSize: block.font_size ? `${block.font_size}pt` : undefined,
                        marginTop: `${block.margin_top_pt || 0}pt`,
                        marginBottom: `${block.margin_bottom_pt || 0}pt`,
                        marginLeft: `${block.indent_left_pt || 0}pt`,
                        marginRight: `${block.indent_right_pt || 0}pt`,
                        textIndent: `${block.first_line_pt || 0}pt`,
                        lineHeight: block.line_height_pt ? `${block.line_height_pt}pt` : block.line_spacing || undefined,
                      }}
                    >
                      <span dangerouslySetInnerHTML={{ __html: block.content }} />
                    </div>
                  )
                })}
              </div>

            </DocxPageSheet>
          ))}
        </div>
      )
    }

    // 2. Fallback: Flattened paragraphs with _page_break markers
    if (preview.paragraphs && Array.isArray(preview.paragraphs)) {
      const pages: Array<Array<{ style: string; content: string; font_name?: string; align?: string }>> = [[]]
      for (const p of preview.paragraphs) {
        const para = typeof p === 'string' ? { style: 'Normal', content: p } : p
        if (para.style === '_page_break') {
          if (pages[pages.length - 1].length > 0) {
            pages.push([])
          }
          continue
        }
        pages[pages.length - 1].push(para)
      }

      return (
        <div className="flex flex-col items-center gap-3.5 w-full py-2">
          {pages.map((pageParas, pageIndex) => (
            <div
              key={pageIndex}
              className="docx-page-sheet"
              style={{
                width: '816px',
                minHeight: '1056px',
                background: '#ffffff',
                boxShadow: '0 8px 25px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.1)',
                position: 'relative',
                boxSizing: 'border-box',
                padding: '64px 72px 64px 72px',
                borderRadius: '2px',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div className="docx-content flex-1">
                {pageParas.map((para, i) => {
                  const styleName = (para.style || 'Normal').toLowerCase()
                  let className = 'docx-para'

                  if (styleName.includes('heading 1') || styleName.includes('title')) {
                    className = 'docx-para docx-h1'
                  } else if (styleName.includes('heading 2')) {
                    className = 'docx-para docx-h2'
                  } else if (styleName.includes('heading 3')) {
                    className = 'docx-para docx-h3'
                  } else if (styleName.includes('heading 4')) {
                    className = 'docx-para docx-h4'
                  } else if (styleName.includes('heading')) {
                    className = 'docx-para docx-h5'
                  }

                  if (!para.content || !para.content.trim()) {
                    return <div key={i} className="docx-para docx-empty-para">&nbsp;</div>
                  }

                  return (
                    <div
                      key={i}
                      className={className}
                      style={{
                        textAlign: (para.align as any) || 'left',
                        fontFamily: para.font_name ? `'${para.font_name}', 'Times New Roman', serif` : undefined,
                      }}
                    >
                      <span dangerouslySetInnerHTML={{ __html: para.content }} />
                    </div>
                  )
                })}
              </div>

            </div>
          ))}
        </div>
      )
    }

    return null
  }

  const renderContent = () => {
    if (loading) {
      return (
        <div className="w-full flex-1 flex items-center justify-center py-20">
          <Loader className="w-9 h-9 text-[#B8E900] animate-spin" />
        </div>
      )
    }

    if (error || (preview && preview.error && !preview.previewable)) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center px-4 w-full">
          <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-3 text-rose-400">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <p className="text-rose-400 font-medium text-sm mb-2">{error || preview?.error}</p>
          <p className="text-xs text-[#94A3B8] max-w-md mb-4">
            Không thể dựng bản xem trước trực tiếp. Bạn vẫn có thể tải tập tin về máy tính bằng nút bên phải.
          </p>
          <Button variant="outline" size="sm" onClick={downloadFile} className="flex items-center gap-2">
            <Download className="w-4 h-4" /> Tải File Về Máy
          </Button>
        </div>
      )
    }

    if (!preview) return null

    if (preview.format && ['md', 'txt'].includes(preview.format)) {
      return (
        <div
          className="docx-page-sheet w-full max-w-[816px] min-h-[1056px] bg-white rounded-[2px] shadow-[0_10px_35px_rgba(0,0,0,0.55),0_0_0_1px_rgba(0,0,0,0.1)] p-16"
        >
          <div className="docx-content">
            <pre className="docx-pre">{preview.content}</pre>
          </div>
        </div>
      )
    }

    if (preview.format === 'csv' && preview.content) {
      const parseCsvToRows = (csvText: string): string[][] => {
        const lines = csvText.split(/\r?\n/).filter((l) => l.trim().length > 0)
        if (lines.length === 0) return []

        // Smart delimiter detection from header/data samples (prefer comma if present as separator)
        const sample = lines.slice(0, 10).join('\n')
        const commaCount = (sample.match(/,/g) || []).length
        const semiCount = (sample.match(/;/g) || []).length
        const tabCount = (sample.match(/\t/g) || []).length

        let delimiter = ','
        if (commaCount > 0 && commaCount >= semiCount) {
          delimiter = ','
        } else if (semiCount > commaCount && semiCount > tabCount) {
          delimiter = ';'
        } else if (tabCount > commaCount && tabCount > semiCount) {
          delimiter = '\t'
        } else {
          delimiter = ','
        }

        return lines.map((line) => {
          const row: string[] = []
          let inQuote = false
          let current = ''
          for (let i = 0; i < line.length; i++) {
            const char = line[i]
            const nextChar = line[i + 1]
            if (char === '"') {
              if (inQuote && nextChar === '"') {
                current += '"'
                i++ // skip escaped quote
              } else {
                inQuote = !inQuote
              }
            } else if (char === delimiter && !inQuote) {
              row.push(current.trim())
              current = ''
            } else {
              current += char
            }
          }
          row.push(current.trim())
          return row
        })
      }

      const csvRows = parseCsvToRows(preview.content)
      return (
        <div className="w-full bg-[#0E1118] rounded-2xl border border-white/10 shadow-2xl p-4 sm:p-6 space-y-4">
          <ScrollableMatrixViewer title="Dữ liệu CSV Bảng Tính" rows={csvRows} />
        </div>
      )
    }

    if (preview.format === 'json') {
      let text = preview.content || '{}'
      try {
        text = JSON.stringify(JSON.parse(preview.content || '{}'), null, 2)
      } catch {}
      return (
        <div
          className="docx-page-sheet w-full max-w-[816px] min-h-[1056px] bg-white rounded-[2px] shadow-[0_10px_35px_rgba(0,0,0,0.55),0_0_0_1px_rgba(0,0,0,0.1)] p-16"
        >
          <div className="docx-content">
            <pre className="docx-pre font-mono text-sm">{text}</pre>
          </div>
        </div>
      )
    }

    if (preview.format === 'html') {
      return (
        <div
          className="docx-page-sheet w-full max-w-[816px] min-h-[850px] h-[850px] bg-white rounded-[2px] shadow-[0_10px_35px_rgba(0,0,0,0.55),0_0_0_1px_rgba(0,0,0,0.1)] overflow-hidden flex flex-col"
        >
          <iframe
            srcDoc={preview.content || ''}
            title="HTML Document Preview"
            className="w-full flex-1 border-0 bg-white"
            sandbox="allow-same-origin allow-scripts"
          />
        </div>
      )
    }

    if (preview.format === 'docx' || preview.format === 'doc') {
      const docxView = renderDocxPages()
      if (docxView) return docxView
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center px-4 w-full text-[#94A3B8]">
          <FileText className="w-10 h-10 mb-3 text-[#64748B]" />
          <p className="text-sm font-medium text-[#F0F6FC] mb-1">Tài liệu không có nội dung văn bản để xem trước</p>
          <p className="text-xs text-[#64748B]">Vui lòng tải file về máy để mở bằng Microsoft Word hoặc WPS Office.</p>
        </div>
      )
    }

    if (preview.format === 'xlsx' && preview.sheets) {
      return (
        <div className="w-full bg-[#0E1118] rounded-2xl border border-white/10 shadow-2xl p-4 sm:p-6 space-y-6">
          {preview.sheets.map((sheet, i) => (
            <ScrollableMatrixViewer
              key={i}
              title={`Trang tính: ${sheet.name}`}
              rows={sheet.data as any}
              cellWarnings={sheet.cell_warnings}
            />
          ))}
        </div>
      )
    }

    if (preview.format === 'pdf') {
      if (pdfLoading) {
        return (
          <div className="w-full flex-1 flex flex-col items-center justify-center py-36 text-[#8E92A4] gap-3">
            <Loader className="w-9 h-9 text-[#B8E900] animate-spin" />
            <p className="text-xs font-mono">Đang tải và dựng tài liệu PDF...</p>
          </div>
        )
      }

      return (
        <div className="w-full h-full min-h-[850px] flex flex-col bg-[#2A2B2E] overflow-hidden rounded-md shadow-2xl">
          <iframe
            src={`${pdfBlobUrl || directDownloadUrl}#toolbar=1&navpanes=0&scrollbar=1`}
            title="PDF Document Viewer"
            className="w-full flex-1 min-h-[850px] border-0 bg-white"
          />
        </div>
      )
    }

    return (
      <div className="docx-page text-center py-8">
        <div className="docx-content">
          <p>Preview not available for this format</p>
        </div>
      </div>
    )
  }

  // ==========================================
  // LOGIC TẢI VỀ & CHIA SẺ (DOWNLOAD & SHARE)
  // ==========================================
  const formatExt = preview?.format === 'markdown' ? 'md' : preview?.format || 'bin'
  const cleanBaseName = customBaseName.trim()
    ? customBaseName.trim().replace(/[\\/:*?"<>|]/g, '_')
    : `fileforge_${jobId.slice(0, 8)}`
  const outputFileName = `${cleanBaseName}.${formatExt}`

  const downloadFile = async () => {
    if (!jobId) return
    setDownloading(true)
    const filename = outputFileName

    try {
      const res = await jobsApi.download(jobId)
      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch {
      fetch(directDownloadUrl)
        .then((res) => res.blob())
        .then((blob) => {
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = filename
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          window.URL.revokeObjectURL(url)
        })
        .catch((err) => console.error('Download failed:', err))
    } finally {
      setDownloading(false)
    }
  }

  const handleCopyLink = () => {
    navigator.clipboard.writeText(directDownloadUrl)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2000)
  }

  const handleCopyJobId = () => {
    navigator.clipboard.writeText(jobId)
    setCopiedJobId(true)
    setTimeout(() => setCopiedJobId(false), 2000)
  }

  const handleCopyContent = () => {
    if (!preview) return
    let textToCopy = preview.content || ''
    if (!textToCopy && preview.paragraphs) {
      textToCopy = preview.paragraphs
        .map((p) => (typeof p === 'string' ? p : p.content))
        .join('\n\n')
    }
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy)
      setCopiedContent(true)
      setTimeout(() => setCopiedContent(false), 2000)
    }
  }

  const isWordDoc = preview?.format === 'docx' || preview?.format === 'doc'
  const hasCopyableText =
    preview &&
    !isWordDoc &&
    preview.format !== 'pdf' &&
    Boolean(preview.content)

  // Render via React Portal to ensure 100% full-screen blur coverage with no cutoffs
  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/80 backdrop-blur-md"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0, y: 10 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.96, opacity: 0, y: 10 }}
        transition={{ duration: 0.2 }}
        className="zzz-device-frame bg-[#14151C] rounded-2xl w-full max-w-7xl h-[92vh] max-h-[920px] overflow-hidden flex flex-col border border-[#282B37] shadow-2xl relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top subtle accent line */}
        <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-[#B8E900]/40 to-transparent" />

        {/* Top Modal Header - ZZZ Hardware Console */}
        <div className="flex items-center justify-between px-5 sm:px-6 py-3.5 border-b border-[#282B37] bg-[#181A22] flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#242733] border border-[#2E313E] flex items-center justify-center text-[#B8E900] shadow-inner">
              <FileText className="w-4 h-4 text-[#B8E900]" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-mono font-bold text-[#B8E900] tracking-widest">
                  .FUNCTIONS //
                </span>
                <h3 className="text-sm sm:text-base font-bold uppercase tracking-wider text-white">
                  DOCUMENT PREVIEW
                </h3>
                <span className="inline-flex items-center justify-center px-2 py-0.5 rounded text-[10px] font-mono font-bold text-[#B8E900] bg-[#B8E900]/10 border border-[#B8E900]/30">
                  {preview?.format?.toUpperCase() || 'LOADING...'}
                </span>
              </div>
              <p className="text-[10px] font-mono text-[#8E92A4] hidden sm:block mt-0.5">
                BUFFER ID: {jobId.slice(0, 16)}...
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              title="Đóng (Esc)"
              className="h-8 px-3 rounded-lg bg-[#242733] hover:bg-rose-500/20 text-[#8E92A4] hover:text-rose-400 border border-[#2E313E] hover:border-rose-500/40 text-xs font-mono font-bold transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
              <span>ESC</span>
            </button>
          </div>
        </div>

        {/* Modal Split View Body: Left = Preview, Right = Actions / Download / Share */}
        <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden bg-[#101116]">
          {/* CỘT TRÁI: PHẦN XEM TRƯỚC (DOCUMENT PREVIEW PANEL) */}
          <div className={`flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 md:p-8 bg-[#101116] flex justify-center ${loading || (preview?.format === 'pdf' && pdfLoading) ? 'items-center' : 'items-start'} border-b lg:border-b-0 lg:border-r border-[#282B37] custom-scrollbar`}>
            <div
              className={`w-full ${preview?.format === 'pdf' ? 'max-w-5xl h-full min-h-[850px]' : preview?.format === 'xlsx' || preview?.format === 'csv' ? 'max-w-6xl' : 'max-w-4xl'} mx-auto flex flex-col ${loading || (preview?.format === 'pdf' && pdfLoading) ? 'h-full justify-center items-center' : 'items-start'}`}
            >
              <style>{`
                .docx-content {
                  font-family: 'Times New Roman', 'Liberation Serif', serif;
                  color: #000000;
                  font-size: 13pt;
                  line-height: 1.45;
                  font-weight: 400;
                }
                .docx-page-sheet {
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                  font-weight: 400;
                }
                .docx-para {
                  margin: 0 0 6pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                  font-size: 13pt;
                  line-height: 1.45;
                  font-weight: 400;
                }
                .docx-empty-para {
                  min-height: 1.25em;
                  margin: 0 0 6pt 0;
                }
                .docx-h1 {
                  font-size: 20pt;
                  font-weight: bold;
                  margin: 16pt 0 6pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                  line-height: 1.3;
                }
                .docx-h2 {
                  font-size: 16pt;
                  font-weight: bold;
                  margin: 14pt 0 4pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                  line-height: 1.3;
                }
                .docx-h3 {
                  font-size: 14pt;
                  font-weight: bold;
                  margin: 10pt 0 3pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                }
                .docx-h4 {
                  font-size: 13pt;
                  font-weight: bold;
                  font-style: italic;
                  margin: 8pt 0 2pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                }
                .docx-h5 {
                  font-size: 12pt;
                  font-weight: bold;
                  margin: 6pt 0 2pt 0;
                  font-family: 'Times New Roman', serif;
                  color: #000000;
                }
                .docx-content strong {
                  font-weight: 700;
                  color: #000000;
                }
                .docx-content em {
                  font-style: italic;
                  color: #000000;
                }
                .docx-content u {
                  text-decoration: underline;
                }
                .docx-content code {
                  font-family: 'Courier New', monospace;
                  background: #f4f4f4;
                  padding: 1px 4px;
                  border-radius: 2px;
                  font-size: 11pt;
                  color: #c7254e;
                }
                .docx-pre {
                  font-family: 'Courier New', monospace;
                  font-size: 11pt;
                  color: #000000;
                  background: transparent;
                  white-space: pre-wrap;
                  word-wrap: break-word;
                  margin: 0;
                  padding: 0;
                }
                .docx-table {
                  border-collapse: collapse;
                  width: 100%;
                  font-family: 'Times New Roman', serif;
                  font-size: 11pt;
                  margin: 8pt 0;
                  color: #000000;
                }
                .docx-table:not(.borderless-table) td, .docx-table:not(.borderless-table) th {
                  border: 1px solid #777777;
                  padding: 4.5pt 6pt;
                  vertical-align: middle;
                  color: #000000;
                }
                .borderless-table, .borderless-table td, .borderless-table th {
                  border: none !important;
                  background: transparent !important;
                }
                .docx-header-row td, .docx-header-row th {
                  background: #f2f4f7;
                  font-weight: bold;
                  color: #000000;
                }
              `}</style>
              {renderContent()}
            </div>
          </div>

          {/* CỘT PHẢI: BẢNG THAO TÁC / TẢI VỀ & CHIA SẺ (ACTIONS / DOWNLOAD & SHARE PANEL) */}
          <div className="w-full lg:w-[360px] xl:w-[390px] flex-shrink-0 bg-[#181A22] border-t lg:border-t-0 lg:border-l border-[#282B37] overflow-y-auto p-5 sm:p-6 flex flex-col justify-between gap-6">
            <div className="space-y-6">
              {/* SECTION: TÊN FILE TẢI VỀ & ĐỔI TÊN FILE (ALWAYS VISIBLE RENAME INPUT) */}
              <div className="zzz-tile p-4 rounded-xl bg-[#242733] border border-[#2E313E] space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-mono uppercase tracking-wider text-[#8E92A4] font-bold flex items-center gap-1.5">
                    <Pencil className="w-3.5 h-3.5 text-[#B8E900]" />
                    Tên file:
                  </label>
                </div>

                {/* Ô nhập tên file trực tiếp */}
                <div className="flex items-center gap-2 p-1.5 rounded-lg bg-[#101116] border border-[#2E313E] focus-within:border-[#B8E900] focus-within:ring-1 focus-within:ring-[#B8E900]/30 transition-all shadow-inner">
                  <input
                    type="text"
                    value={customBaseName}
                    onChange={(e) => setCustomBaseName(e.target.value)}
                    placeholder="Nhập tên file bạn muốn tải về..."
                    className="flex-1 bg-transparent px-2.5 py-1 text-xs font-mono text-white outline-none select-all"
                  />
                  <span className="px-2.5 py-1 rounded bg-[#B8E900]/10 text-[#B8E900] border border-[#B8E900]/30 text-xs font-mono font-bold select-none">
                    .{formatExt}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] font-mono text-[#8E92A4]">
                  <span>Định dạng: <strong className="text-[#B8E900]">{preview?.format?.toUpperCase() || '...'}</strong></span>
                  {customBaseName !== `fileforge_${jobId.slice(0, 8)}` && (
                    <button
                      type="button"
                      onClick={() => setCustomBaseName(`fileforge_${jobId.slice(0, 8)}`)}
                      className="text-[#8E92A4] hover:text-[#B8E900] flex items-center gap-1 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Đặt lại tên mặc định</span>
                    </button>
                  )}
                </div>
              </div>

              {/* SECTION: TẢI VỀ (DOWNLOAD SECTION) */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono uppercase tracking-wider text-[#8E92A4] font-bold flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5 text-[#B8E900]" />
                    Tải Về Máy
                  </h4>
                </div>

                <button
                  type="button"
                  className="btn-zzz-primary w-full py-3.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 cursor-pointer"
                  onClick={downloadFile}
                  disabled={downloading}
                >
                  {downloading ? (
                    <>
                      <Loader className="w-4 h-4 animate-spin text-black" />
                      <span>ĐANG TẢI XUỐNG...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4 text-black" />
                      <span>TẢI TẬP TIN VỀ MÁY</span>
                    </>
                  )}
                </button>

                {hasCopyableText && (
                  <button
                    onClick={handleCopyContent}
                    className="w-full py-2.5 px-3 rounded-xl bg-[#242733] hover:bg-[#282B37] text-white border border-[#2E313E] text-xs font-mono font-medium transition-all flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {copiedContent ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-[#B8E900]" />
                        <span className="text-[#B8E900]">ĐÃ SAO CHÉP THÀNH CÔNG</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-[#8E92A4]" />
                        <span>SAO CHÉP TOÀN BỘ VĂN BẢN</span>
                      </>
                    )}
                  </button>
                )}
              </div>

              {/* SECTION: CHIA SẺ LIÊN KẾT (SHARE LINK FILE) */}
              <div className="space-y-3 pt-2 border-t border-[#282B37]">
                <h4 className="text-xs font-mono uppercase tracking-wider text-[#8E92A4] font-bold flex items-center gap-1.5">
                  <Share2 className="w-3.5 h-3.5 text-[#B8E900]" />
                  Chia Sẻ Liên Kết File
                </h4>

                <p className="text-[11px] text-[#8E92A4]">
                  Đường dẫn tải trực tiếp tập tin hoặc chia sẻ nội bộ:
                </p>

                <div className="flex items-center gap-1.5 p-1.5 rounded-lg bg-[#101116] border border-[#2E313E]">
                  <input
                    type="text"
                    readOnly
                    value={directDownloadUrl}
                    className="flex-1 bg-transparent px-2 text-xs font-mono text-[#8E92A4] outline-none select-all truncate"
                  />
                  <button
                    onClick={handleCopyLink}
                    title="Sao chép link tải"
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-mono font-medium bg-[#242733] hover:bg-[#282B37] text-[#B8E900] border border-[#2E313E] transition-all flex-shrink-0 cursor-pointer"
                  >
                    {copiedLink ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-[#B8E900]" />
                        <span className="text-[#B8E900]">Đã copy!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Link</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* SECTION: METADATA & SYSTEM SPECS */}
              <div className="space-y-2 pt-2 border-t border-[#282B37] text-xs font-mono text-[#8E92A4]">
                <div className="flex items-center justify-between py-1">
                  <span>Mã tác vụ (Job ID):</span>
                  <button
                    onClick={handleCopyJobId}
                    className="flex items-center gap-1 text-[#8E92A4] hover:text-[#B8E900] transition-colors cursor-pointer"
                  >
                    <span>{jobId.slice(0, 10)}...</span>
                    {copiedJobId ? (
                      <Check className="w-3 h-3 text-[#B8E900]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>

                {formatExecutionDuration(preview?.started_at, preview?.completed_at, preview?.duration_seconds) && (
                  <div className="flex items-center justify-between py-1">
                    <span>Thời gian chuyển đổi:</span>
                    <span className="text-[#B8E900] font-medium flex items-center gap-1 font-mono">
                      <Clock className="w-3 h-3 text-[#B8E900]" />
                      {formatExecutionDuration(preview?.started_at, preview?.completed_at, preview?.duration_seconds)}
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between py-1">
                  <span>Kiến trúc xử lý:</span>
                  <span className="text-white flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-[#B8E900]" />
                    FileForge AST Engine
                  </span>
                </div>

                <div className="flex items-center justify-between py-1">
                  <span>Bảo mật dữ liệu:</span>
                  <span className="text-white flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-[#B8E900]" />
                    Zero-Retention Memory
                  </span>
                </div>
              </div>
            </div>

            {/* Bottom Footer Note */}
            <div className="pt-3 border-t border-[#282B37] text-[10px] font-mono text-[#8E92A4] text-center">
              Nhấn phím <kbd className="px-1.5 py-0.5 rounded bg-[#242733] border border-[#2E313E] text-white">ESC</kbd> hoặc nhấp bên ngoài để đóng
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>,
    document.body
  )
}
