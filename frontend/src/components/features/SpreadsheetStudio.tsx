import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Table as TableIcon,
  Sliders,
  Zap,
  Database,
  FileSpreadsheet,
  Layers,
  Crop,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Eye,
  Loader2,
  Maximize2,
  Minimize2,
  Check,
  FileText,
} from 'lucide-react'
import { Button } from '../ui/button'
import DropZone from '../ui/dropzone'
import { spreadsheetApi, filesApi, jobsApi } from '../../lib/api'
import { Job, SpreadsheetOptions } from '../../types'
import { formatBytes } from '../../lib/utils'
import toast from 'react-hot-toast'

export interface StagedSpreadsheetItem {
  id?: string
  name: string
  size: number
  rawFile?: File
}

export interface SpreadsheetStudioProps {
  initialFiles?: any[]
  onJobCreated: (job: Job) => void
}

export interface SheetPreviewItem {
  name: string
  data: (string | number | null)[][]
  total_rows?: number
  total_cols?: number
}

// Coordinate Helper Functions
const colIndexToLetter = (index: number): string => {
  let letter = ''
  let temp = index
  while (temp >= 0) {
    letter = String.fromCharCode((temp % 26) + 65) + letter
    temp = Math.floor(temp / 26) - 1
  }
  return letter
}

const letterToColIndex = (letter: string): number => {
  let index = 0
  const clean = letter.toUpperCase().trim()
  for (let i = 0; i < clean.length; i++) {
    index = index * 26 + (clean.charCodeAt(i) - 64)
  }
  return index - 1
}

const parseRangeCoordinates = (rangeStr?: string) => {
  if (!rangeStr || !rangeStr.includes(':')) return null
  const parts = rangeStr.trim().toUpperCase().split(':')
  if (parts.length !== 2) return null
  const m1 = parts[0].match(/^([A-Z]+)(\d+)$/)
  const m2 = parts[1].match(/^([A-Z]+)(\d+)$/)
  if (!m1 || !m2) return null

  const col1 = letterToColIndex(m1[1])
  const row1 = parseInt(m1[2], 10)
  const col2 = letterToColIndex(m2[1])
  const row2 = parseInt(m2[2], 10)

  return {
    minCol: Math.min(col1, col2),
    maxCol: Math.max(col1, col2),
    minRow: Math.min(row1, row2),
    maxRow: Math.max(row1, row2),
  }
}

export default function SpreadsheetStudio({ initialFiles, onJobCreated }: SpreadsheetStudioProps) {
  const [selectedFile, setSelectedFile] = useState<StagedSpreadsheetItem | null>(null)
  const [outputFormat, setOutputFormat] = useState<'json' | 'csv' | 'xlsx'>('xlsx')
  const [includeHeader, setIncludeHeader] = useState(true)
  const [delimiter, setDelimiter] = useState<',' | ';' | '\t'>(',')
  const [indent, setIndent] = useState<2 | 4>(2)
  const [isProcessing, setIsProcessing] = useState(false)

  // Range & Sheet Selection States
  const [selectedSheet, setSelectedSheet] = useState<string>('')
  const [rangeMode, setRangeMode] = useState<'all' | 'custom' | 'first50' | 'first100'>('all')
  const [cellRange, setCellRange] = useState<string>('')
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Interactive Mouse Drag-to-Select States
  const [isSelecting, setIsSelecting] = useState(false)
  const [dragStartCell, setDragStartCell] = useState<{ row: number; col: number } | null>(null)
  const [colDragStart, setColDragStart] = useState<number | null>(null)
  const [rowDragStart, setRowDragStart] = useState<number | null>(null)

  // Live Sheet Preview States
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewSheets, setPreviewSheets] = useState<SheetPreviewItem[]>([])

  const matrixScrollRef = useRef<HTMLDivElement>(null)
  const fullscreenScrollRef = useRef<HTMLDivElement>(null)

  // Virtual Scrolling Engine Constants & States (Handles up to 1,000,000 rows with 60 FPS)
  const ROW_HEIGHT = 33
  const OVERSCAN = 15
  const [matrixScrollTop, setMatrixScrollTop] = useState(0)
  const [fullscreenScrollTop, setFullscreenScrollTop] = useState(0)

  const allSpreadsheetFormats: Array<{ id: 'json' | 'csv' | 'xlsx'; label: string }> = [
    { id: 'xlsx', label: 'XLSX (Excel)' },
    { id: 'csv', label: 'CSV (UTF-8 BOM)' },
    { id: 'json', label: 'JSON Schema' },
  ]

  const getInputSpreadsheetFormat = (filename?: string): string => {
    if (!filename) return ''
    const ext = filename.split('.').pop()?.toLowerCase() || ''
    if (ext === 'xlsx' || ext === 'xls') return 'xlsx'
    if (ext === 'csv' || ext === 'tsv') return 'csv'
    if (ext === 'json') return 'json'
    if (ext === 'ods') return 'ods'
    return ''
  }

  // Handle Initial Files from Landing Page
  useEffect(() => {
    if (initialFiles && initialFiles.length > 0) {
      const first = initialFiles[0]
      const name = first.original_filename || first.name || 'document.csv'
      const size = first.file_size || first.size || 0
      const id = first.id
      const staged: StagedSpreadsheetItem = {
        id,
        name,
        size,
        rawFile: first instanceof File ? first : undefined,
      }
      setSelectedFile(staged)

      const inExt = getInputSpreadsheetFormat(name)
      if (inExt === 'xlsx') setOutputFormat('csv')
      else if (inExt === 'csv') setOutputFormat('xlsx')
      else if (inExt === 'json') setOutputFormat('xlsx')
      else setOutputFormat('json')

      fetchFilePreview(staged)
    } else {
      setSelectedFile(null)
      setPreviewSheets([])
      setCellRange('')
      setRangeMode('all')
    }
  }, [initialFiles])

  // Fetch Live Preview when file is staged
  const fetchFilePreview = async (staged: StagedSpreadsheetItem) => {
    setPreviewLoading(true)
    setPreviewSheets([])
    try {
      let fileId = staged.id
      if (!fileId && staged.rawFile) {
        const uploadRes = await filesApi.upload([staged.rawFile])
        fileId = uploadRes.data.files[0]?.id
        setSelectedFile((prev) => (prev ? { ...prev, id: fileId } : null))
      }

      if (fileId) {
        const res = await spreadsheetApi.preview({
          input_file_id: fileId,
        })
        if (res.data?.sheets && res.data.sheets.length > 0) {
          setPreviewSheets(res.data.sheets)
          setSelectedSheet(res.data.sheets[0].name)
        }
      }
    } catch (e) {
      console.warn('Failed to load spreadsheet preview:', e)
    } finally {
      setPreviewLoading(false)
    }
  }

  // Column Width States for interactive resizing
  const [colWidths, setColWidths] = useState<{ [key: number]: number }>({})

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

  // Smooth Edge Auto-scroll when mouse dragging selection near/outside container
  useEffect(() => {
    if (!isSelecting) return

    let animationFrameId: number
    let lastClientX = 0
    let lastClientY = 0
    let hasMoved = false
    let startX = 0
    let startY = 0
    let first = true

    const handleMouseMove = (e: MouseEvent) => {
      if (first) {
        startX = e.clientX
        startY = e.clientY
        first = false
      }
      if (Math.abs(e.clientX - startX) > 6 || Math.abs(e.clientY - startY) > 6) {
        hasMoved = true
      }
      lastClientX = e.clientX
      lastClientY = e.clientY
    }

    const autoScroll = () => {
      const container = isFullscreen ? fullscreenScrollRef.current : matrixScrollRef.current
      if (container && isSelecting && hasMoved) {
        const rect = container.getBoundingClientRect()
        const maxScrollSpeed = 22

        if (lastClientX > rect.right - 25) {
          const dist = Math.max(1, lastClientX - (rect.right - 25))
          container.scrollLeft += Math.min(maxScrollSpeed, dist * 0.3)
        } else if (lastClientX < rect.left + 25) {
          const dist = Math.max(1, (rect.left + 25) - lastClientX)
          container.scrollLeft -= Math.min(maxScrollSpeed, dist * 0.3)
        }

        if (lastClientY > rect.bottom - 25) {
          const dist = Math.max(1, lastClientY - (rect.bottom - 25))
          container.scrollTop += Math.min(maxScrollSpeed, dist * 0.3)
        } else if (lastClientY < rect.top + 25) {
          const dist = Math.max(1, (rect.top + 25) - lastClientY)
          container.scrollTop -= Math.min(maxScrollSpeed, dist * 0.3)
        }
      }
      animationFrameId = requestAnimationFrame(autoScroll)
    }

    window.addEventListener('mousemove', handleMouseMove)
    animationFrameId = requestAnimationFrame(autoScroll)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      cancelAnimationFrame(animationFrameId)
    }
  }, [isSelecting, isFullscreen])

  // Lock body scroll when fullscreen is open to prevent background scroll
  useEffect(() => {
    if (isFullscreen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isFullscreen])

  // Global mouse up listener for drag selection
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsSelecting(false)
      setColDragStart(null)
      setRowDragStart(null)
    }
    window.addEventListener('mouseup', handleGlobalMouseUp)
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp)
  }, [])

  const inputSpreadsheetExt = getInputSpreadsheetFormat(selectedFile?.name)
  const availableSpreadsheetFormats = selectedFile
    ? allSpreadsheetFormats.filter((fmt) => fmt.id !== inputSpreadsheetExt)
    : allSpreadsheetFormats

  const handleFiles = (files: File[]) => {
    if (files.length > 0) {
      const file = files[0]
      const staged: StagedSpreadsheetItem = {
        name: file.name,
        size: file.size,
        rawFile: file,
      }
      setSelectedFile(staged)
      setRangeMode('all')
      setCellRange('')

      const inExt = getInputSpreadsheetFormat(file.name)
      if (inExt === 'xlsx') setOutputFormat('csv')
      else if (inExt === 'csv') setOutputFormat('xlsx')
      else if (inExt === 'json') setOutputFormat('xlsx')
      else setOutputFormat('json')

      fetchFilePreview(staged)
    }
  }

  // Mouse Drag Selection Handlers
  const handleCellMouseDown = (rowNum: number, colIdx: number) => {
    setIsSelecting(true)
    setDragStartCell({ row: rowNum, col: colIdx })
    setColDragStart(null)
    setRowDragStart(null)
    const colLetter = colIndexToLetter(colIdx)
    const range = `${colLetter}${rowNum}:${colLetter}${rowNum}`
    setCellRange(range)
    setRangeMode('custom')
  }

  const handleCellMouseEnter = (rowNum: number, colIdx: number) => {
    if (isSelecting && dragStartCell) {
      const minR = Math.min(dragStartCell.row, rowNum)
      const maxR = Math.max(dragStartCell.row, rowNum)
      const minC = Math.min(dragStartCell.col, colIdx)
      const maxC = Math.max(dragStartCell.col, colIdx)

      const startColLet = colIndexToLetter(minC)
      const endColLet = colIndexToLetter(maxC)
      const range = `${startColLet}${minR}:${endColLet}${maxR}`
      setCellRange(range)
      setRangeMode('custom')
    }
  }

  // Column Header Click & Drag Handlers
  const handleColHeaderMouseDown = (colIdx: number) => {
    setIsSelecting(true)
    setColDragStart(colIdx)
    setDragStartCell(null)
    setRowDragStart(null)
    const colLetter = colIndexToLetter(colIdx)
    // Use effectiveTotalRows (from backend total_rows) to avoid off-by-one errors
    setCellRange(`${colLetter}1:${colLetter}${effectiveTotalRows}`)
    setRangeMode('custom')
  }

  const handleColHeaderMouseEnter = (colIdx: number) => {
    if (isSelecting && colDragStart !== null) {
      const minC = Math.min(colDragStart, colIdx)
      const maxC = Math.max(colDragStart, colIdx)
      setCellRange(`${colIndexToLetter(minC)}1:${colIndexToLetter(maxC)}${effectiveTotalRows}`)
      setRangeMode('custom')
    }
  }

  // Row Header Click & Drag Handlers
  const handleRowHeaderMouseDown = (rowNum: number) => {
    setIsSelecting(true)
    setRowDragStart(rowNum)
    setDragStartCell(null)
    setColDragStart(null)
    const totalCols = (currentSheetData?.data[0]?.length || 1) - 1
    const endColLet = colIndexToLetter(Math.max(0, totalCols))
    setCellRange(`A${rowNum}:${endColLet}${rowNum}`)
    setRangeMode('custom')
  }

  const handleRowHeaderMouseEnter = (rowNum: number) => {
    if (isSelecting && rowDragStart !== null) {
      const minR = Math.min(rowDragStart, rowNum)
      const maxR = Math.max(rowDragStart, rowNum)
      const totalCols = (currentSheetData?.data[0]?.length || 1) - 1
      const endColLet = colIndexToLetter(Math.max(0, totalCols))
      setCellRange(`A${minR}:${endColLet}${maxR}`)
      setRangeMode('custom')
    }
  }

  // Check if Cell is selected
  const isCellSelected = (rowNum: number, colIdx: number): boolean => {
    if (rangeMode === 'all') return false
    if (rangeMode === 'first50') return rowNum <= 50
    if (rangeMode === 'first100') return rowNum <= 100
    if (rangeMode === 'custom') {
      const bounds = parseRangeCoordinates(cellRange)
      if (bounds) {
        return (
          rowNum >= bounds.minRow &&
          rowNum <= bounds.maxRow &&
          colIdx >= bounds.minCol &&
          colIdx <= bounds.maxCol
        )
      }
    }
    return false
  }

  // Horizontal Scroll Handlers
  const handleScrollLeft = () => {
    matrixScrollRef.current?.scrollBy({ left: -350, behavior: 'smooth' })
  }
  const handleScrollRight = () => {
    matrixScrollRef.current?.scrollBy({ left: 350, behavior: 'smooth' })
  }
  const handleScrollStart = () => {
    matrixScrollRef.current?.scrollTo({ left: 0, behavior: 'smooth' })
  }
  const handleScrollEnd = () => {
    if (matrixScrollRef.current) {
      matrixScrollRef.current.scrollTo({
        left: matrixScrollRef.current.scrollWidth,
        behavior: 'smooth',
      })
    }
  }

  // Compute Active Range Expression
  const getComputedRange = (): string | undefined => {
    if (rangeMode === 'all') return undefined
    if (rangeMode === 'first50') return 'A1:Z50'
    if (rangeMode === 'first100') return 'A1:Z100'
    if (rangeMode === 'custom') {
      if (cellRange.trim()) return cellRange.trim().toUpperCase()
    }
    return undefined
  }

  const handleConvert = async () => {
    if (!selectedFile) {
      toast.error('Vui lòng chọn file bảng tính (XLSX, CSV, JSON)')
      return
    }

    setIsProcessing(true)
    try {
      let inputFileId = selectedFile.id
      if (!inputFileId && selectedFile.rawFile) {
        const uploadRes = await filesApi.upload([selectedFile.rawFile])
        inputFileId = uploadRes.data.files[0].id
      }
      if (!inputFileId) {
        toast.error('Không tìm thấy tệp tin hợp lệ để chuyển đổi')
        return
      }

      const activeRange = getComputedRange()

      // Convert Spreadsheet Options
      const options: SpreadsheetOptions = {
        sheet_name: selectedSheet || undefined,
        cell_range: activeRange,
        include_header: includeHeader,
        delimiter,
        indent,
      }

      const res = await spreadsheetApi.convert({
        input_file_id: inputFileId,
        output_format: outputFormat,
        options,
      })

      const job = res.data
      toast.success(
        activeRange
          ? `Đã chuyển đổi thành công vùng ô [${activeRange}]!`
          : 'Chuyển đổi ma trận dữ liệu thành công!'
      )
      onJobCreated(job)

      // Auto download if enabled
      if (localStorage.getItem('fileforge_auto_download') === 'true') {
        try {
          const dlRes = await jobsApi.download(job.id)
          const blob = new Blob([dlRes.data])
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `matrix_${job.id.slice(0, 8)}.${outputFormat}`
          a.click()
          window.URL.revokeObjectURL(url)
        } catch {
          // silently catch
        }
      }

      setSelectedFile(null)
      setPreviewSheets([])
    } catch (err: any) {
      toast.error(err.response?.data?.detail || err.message || 'Lỗi khi xử lý bảng tính')
    } finally {
      setIsProcessing(false)
    }
  }

  const currentSheetData = previewSheets.find((s) => s.name === selectedSheet) || previewSheets[0]

  // Virtual Scrolling Window Calculation (Handles up to 1,000,000 rows at 60 FPS)
  // Use total_rows from backend (actual Excel row count) when available; fallback to data.length
  const rawDataRows = currentSheetData && currentSheetData.data ? currentSheetData.data : []
  const totalDataRows = rawDataRows.length
  // Use backend's total_rows if available, otherwise compute from raw data length
  // This ensures row selection uses the correct Excel row count
  const effectiveTotalRows = currentSheetData?.total_rows ?? totalDataRows
  const totalCols = currentSheetData && currentSheetData.data[0] ? currentSheetData.data[0].length : 0

  // Regular View Virtual Window
  const matrixVisibleCount = 20
  const matrixStartIndex = Math.max(0, Math.floor(matrixScrollTop / ROW_HEIGHT) - OVERSCAN)
  const matrixEndIndex = Math.min(totalDataRows, matrixStartIndex + matrixVisibleCount + (OVERSCAN * 2))
  const matrixVisibleRows = rawDataRows.slice(matrixStartIndex, matrixEndIndex)
  const matrixTopSpacer = matrixStartIndex * ROW_HEIGHT
  const matrixBottomSpacer = Math.max(0, (totalDataRows - matrixEndIndex) * ROW_HEIGHT)

  // Fullscreen View Virtual Window
  const fsVisibleCount = 35
  const fsStartIndex = Math.max(0, Math.floor(fullscreenScrollTop / ROW_HEIGHT) - OVERSCAN)
  const fsEndIndex = Math.min(totalDataRows, fsStartIndex + fsVisibleCount + (OVERSCAN * 2))
  const fsVisibleRows = rawDataRows.slice(fsStartIndex, fsEndIndex)
  const fsTopSpacer = fsStartIndex * ROW_HEIGHT
  const fsBottomSpacer = Math.max(0, (totalDataRows - fsEndIndex) * ROW_HEIGHT)

  return (
    <div className="zzz-device-frame p-5 sm:p-7 space-y-5 max-w-full overflow-hidden min-w-0 shadow-2xl">
      {/* Studio Header */}
      <div className="flex items-center justify-between border-b border-[#282B37] pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-[#B8E900] flex-shrink-0">
            <TableIcon className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base sm:text-lg font-bold font-tech uppercase tracking-wider text-white truncate">
              BẢNG TÍNH & MATRIX LAB // SPREADSHEET
            </h3>
            <p className="text-xs font-mono text-[#9CA3AF] truncate">
              Quét chọn vùng ô trực tiếp bằng chuột, chuyển đổi linh hoạt theo Sheet giữa Excel, CSV & JSON
            </p>
          </div>
        </div>

        <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono bg-[#222530] text-white border border-[#2E313E] flex-shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900] animate-pulse" />
          <span>MATRIX SCANNER</span>
        </span>
      </div>

      {/* Upload Zone / Staged Cockpit */}
      {!selectedFile ? (
        <DropZone
          onFilesSelected={handleFiles}
          isLoading={isProcessing}
          acceptTypes={['.xlsx', '.xls', '.csv', '.json', '.ods']}
          helperText="Hỗ trợ bảng tính Excel (.xlsx, .xls), CSV (.csv), JSON Data (.json), OpenDocument (.ods)"
        />
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="space-y-4 max-w-full min-w-0"
        >
          {/* Staging Cockpit Card */}
          <div className="rounded-2xl bg-[#14151C] border border-[#282B37] p-5 sm:p-6 space-y-4 select-none max-w-full min-w-0 shadow-xl">
            {/* Staged File Identity Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-[#282B37] max-w-full">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white flex-shrink-0">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold font-tech uppercase tracking-wider text-white truncate">
                      {selectedFile.name}
                    </h4>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#222530] text-[#B8E900] border border-[#2E313E] flex-shrink-0">
                      SẴN SÀNG
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-[#9CA3AF] mt-0.5">
                    <span>{formatBytes(selectedFile.size)}</span>
                    <span>•</span>
                    <div className="flex items-center gap-1">
                      <span className="px-1.5 py-0.5 rounded bg-[#222530] text-[#9CA3AF] border border-[#2E313E] uppercase">
                        {selectedFile.name.split('.').pop()?.toUpperCase()}
                      </span>
                      <span className="text-[#B8E900]">➔</span>
                      <span className="px-2 py-0.5 rounded-full bg-[#B8E900] text-[#0C0D10] font-black uppercase text-[10px]">
                        {outputFormat.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
                <label className="cursor-pointer px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase bg-[#222530] hover:bg-[#2B2E3C] text-white border border-[#2E313E] hover:border-white transition-colors">
                  <span>ĐỔI TỆP</span>
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv,.json,.ods"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        handleFiles(Array.from(e.target.files))
                      }
                    }}
                  />
                </label>
                <button
                  onClick={() => {
                    setSelectedFile(null)
                    setPreviewSheets([])
                  }}
                  className="px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase bg-[#2A1518] text-[#FF4D6D] hover:bg-[#381B20] border border-[#FF4D6D]/30 transition-colors"
                >
                  HỦY
                </button>
              </div>
            </div>

            {/* Compact Range & Sheet Selector Bar */}
            <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-tech font-bold uppercase text-white mr-1 flex items-center gap-1.5">
                  <Crop className="w-3.5 h-3.5 text-[#B8E900]" /> VÙNG XUẤT:
                </span>
                {[
                  { id: 'all', label: 'Toàn bộ sheet' },
                  { id: 'first50', label: '50 dòng' },
                  { id: 'first100', label: '100 dòng' },
                  { id: 'custom', label: 'Quét tọa độ' },
                ].map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => {
                      setRangeMode(mode.id as any)
                      if (mode.id === 'all') setCellRange('')
                    }}
                    className={`px-3 py-1 rounded-full text-xs font-tech font-bold uppercase transition-all ${
                      rangeMode === mode.id
                        ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                        : 'bg-[#222530] text-[#9CA3AF] hover:text-white border border-[#2E313E]'
                    }`}
                  >
                    {mode.label}
                  </button>
                ))}

                {rangeMode === 'custom' && (
                  <div className="flex items-center gap-1.5 ml-1">
                    <input
                      type="text"
                      value={cellRange}
                      onChange={(e) => setCellRange(e.target.value)}
                      placeholder="VD: A1:H30"
                      className="px-2.5 py-1 rounded-xl bg-[#222530] border border-[#B8E900] text-xs font-mono text-white placeholder:text-[#6B7280] focus:outline-none w-28 uppercase font-bold text-center"
                    />
                    {cellRange && (
                      <button
                        type="button"
                        onClick={() => {
                          setCellRange('')
                          setRangeMode('all')
                        }}
                        className="px-2 py-0.5 rounded-lg bg-[#2A1518] text-[#FF4D6D] text-[10px] font-mono hover:bg-[#381B20]"
                      >
                        Xóa
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Sheet Switcher */}
              {previewSheets.length > 1 && (
                <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar">
                  <span className="text-xs font-tech font-bold uppercase text-white mr-0.5 flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-[#B8E900]" /> SHEET:
                  </span>
                  {previewSheets.map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onClick={() => setSelectedSheet(s.name)}
                      className={`px-3 py-1 rounded-full text-xs font-tech font-bold uppercase transition-all whitespace-nowrap ${
                        selectedSheet === s.name
                          ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                          : 'bg-[#222530] text-[#9CA3AF] hover:text-white border border-[#2E313E]'
                      }`}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Live Interactive Matrix Inspector & Visual Drag-Selector */}
            <div className="rounded-xl bg-[#07090E] border border-white/10 overflow-hidden shadow-2xl space-y-0">
              {/* Toolbar */}
              <div className="px-3.5 py-2.5 bg-[#181A22] border-b border-[#282B37] flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Eye className="w-3.5 h-3.5 text-[#B8E900]" />
                  <h4 className="text-xs font-bold font-tech uppercase text-white flex items-center gap-1.5">
                    <span>XEM TRƯỚC:</span>
                    <span className="text-[#B8E900]">{currentSheetData?.name || 'Sheet1'}</span>
                  </h4>
                  {previewLoading && <Loader2 className="w-3 h-3 text-[#B8E900] animate-spin ml-1" />}
                </div>

                {/* Horizontal Navigation & Fullscreen */}
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="flex items-center bg-[#222530] border border-[#2E313E] rounded-xl p-0.5 text-xs font-mono">
                    <button
                      type="button"
                      onClick={handleScrollStart}
                      title="Về cột đầu tiên (Cột A)"
                      className="px-2 py-1 hover:bg-white/10 rounded-lg text-[#9CA3AF] hover:text-white transition-colors"
                    >
                      <ChevronsLeft className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={handleScrollLeft}
                      title="Cuộn sang trái (-350px)"
                      className="px-2 py-1 hover:bg-white/10 rounded-lg text-[#9CA3AF] hover:text-white font-bold transition-colors flex items-center gap-0.5"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" /> Trái
                    </button>
                    <div className="w-[1px] h-3 bg-white/10 my-auto mx-0.5" />
                    <button
                      type="button"
                      onClick={handleScrollRight}
                      title="Cuộn sang phải (+350px)"
                      className="px-2 py-1 hover:bg-white/10 rounded-lg text-[#9CA3AF] hover:text-white font-bold transition-colors flex items-center gap-0.5"
                    >
                      Phải <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={handleScrollEnd}
                      title="Đến cột cuối cùng"
                      className="px-2 py-1 hover:bg-white/10 rounded-lg text-[#9CA3AF] hover:text-white transition-colors"
                    >
                      <ChevronsRight className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsFullscreen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#222530] border border-[#2E313E] hover:border-white text-white text-xs font-tech font-bold uppercase transition-all shadow-sm"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                    <span>Toàn màn hình</span>
                  </button>

                  <div className="flex items-center gap-1.5 text-[11px] font-mono">
                    <span className="px-2 py-0.5 rounded-full bg-[#222530] border border-[#2E313E] text-white">
                      {currentSheetData ? `${currentSheetData.data.length} hàng` : '0 hàng'}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-[#222530] border border-[#2E313E] text-[#B8E900]">
                      {currentSheetData && currentSheetData.data[0] ? `${currentSheetData.data[0].length} cột` : '0 cột'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Matrix Table Sub-bar */}
              <div className="px-3.5 py-1.5 bg-[#14151C] border-b border-[#282B37] flex items-center justify-between text-[11px] font-mono text-[#9CA3AF]">
                <span>💡 Kéo chuột để quét tọa độ • Nhấp <code className="text-white">[A], [B]</code> hoặc số dòng <code className="text-white">#</code> để chọn</span>
                <div>
                  {cellRange ? (() => {
                    const bounds = parseRangeCoordinates(cellRange)
                    const count = bounds ? bounds.maxRow - bounds.minRow + 1 : null
                    return (
                      <span className="text-[#B8E900] font-bold bg-[#222530] px-2.5 py-0.5 rounded-full border border-[#2E313E]">
                        Đang chọn: [{cellRange}] {count ? `• ${count} dòng (#${bounds?.minRow} → #${bounds?.maxRow})` : ''}
                      </span>
                    )
                  })() : (
                    <span className="text-[#9CA3AF]">Toàn bộ sheet ({effectiveTotalRows} dòng)</span>
                  )}
                </div>
              </div>

              {/* Massive Interactive Matrix Table with Cell Drag Selection & Virtual 1M-Row Scrolling */}
              <div
                ref={matrixScrollRef}
                onScroll={(e) => setMatrixScrollTop(e.currentTarget.scrollTop)}
                className="w-full max-w-full overflow-x-auto overflow-y-auto min-h-[240px] max-h-[330px] bg-white custom-scrollbar select-none cursor-cell will-change-scroll relative"
              >
                {previewLoading ? (
                  <div className="flex flex-col items-center justify-center py-28 text-slate-500 gap-3">
                    <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                    <p className="text-sm font-mono font-bold text-slate-700">Đang tải ma trận bảng tính để quét tọa độ...</p>
                  </div>
                ) : currentSheetData && currentSheetData.data.length > 0 ? (
                  <table className="border-collapse text-xs font-sans table-fixed" style={{ width: 'max-content' }}>
                    <colgroup>
                      <col style={{ width: '48px', minWidth: '48px', maxWidth: '48px' }} />
                      {Array.from({ length: totalCols }).map((_, ci) => {
                        const width = colWidths[ci] || 130
                        return (
                          <col
                            key={`col-w-${ci}`}
                            style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                          />
                        )
                      })}
                    </colgroup>
                    <thead className="bg-[#E2E8F0] sticky top-0 z-10 shadow-sm border-b-2 border-slate-300 select-none">
                      <tr>
                        <th className="w-12 px-2.5 py-1.5 text-center text-[11px] font-mono font-bold text-slate-600 bg-[#CBD5E1] border-r border-slate-300 select-none sticky left-0 z-20">
                          #
                        </th>
                        {Array.from({ length: totalCols }).map((_, ci) => {
                          const colLetter = colIndexToLetter(ci)
                          const width = colWidths[ci] || 130
                          return (
                            <th
                              key={`th-col-${ci}`}
                              style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                              onMouseDown={() => handleColHeaderMouseDown(ci)}
                              onMouseEnter={() => handleColHeaderMouseEnter(ci)}
                              title={`Kéo hoặc nhấp để chọn Cột [${colLetter}]`}
                              className="relative px-2.5 py-1.5 text-center text-xs font-mono font-bold text-slate-800 border-r border-slate-300 bg-[#E2E8F0] hover:bg-emerald-100 transition-colors whitespace-nowrap cursor-pointer select-none group overflow-visible"
                            >
                              <span className="text-[11px] text-emerald-700 font-mono font-bold bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30">
                                [{colLetter}]
                              </span>
                              {/* Column Resizer Handle */}
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
                    </thead>
                    <tbody className="divide-y divide-slate-200 bg-white">
                      {matrixTopSpacer > 0 && (
                        <tr style={{ height: `${matrixTopSpacer}px` }} aria-hidden="true">
                          <td colSpan={totalCols + 1} className="p-0 border-0 pointer-events-none" />
                        </tr>
                      )}
                      {matrixVisibleRows.map((row, index) => {
                        const ri = matrixStartIndex + index
                        const rowNum = ri + 1 // Excel Row number: 1, 2, 3, 4...
                        return (
                          <tr key={`row-${ri}`} className="transition-colors h-[30px]">
                            {/* Row Header Indicator */}
                            <td
                              onMouseDown={() => handleRowHeaderMouseDown(rowNum)}
                              onMouseEnter={() => handleRowHeaderMouseEnter(rowNum)}
                              title={`Kéo hoặc nhấp để chọn Dòng #${rowNum}`}
                              className="px-2.5 py-1 text-center text-[11px] font-mono font-bold text-slate-500 bg-slate-100 hover:bg-emerald-100 border-r border-slate-300 select-none sticky left-0 z-10 cursor-pointer transition-colors"
                            >
                              {rowNum}
                            </td>

                            {/* Data Cells with Drag-to-Select */}
                            {row.map((cell, ci) => {
                              const isSelected = isCellSelected(rowNum, ci)
                              return (
                                <td
                                  key={`cell-${ri}-${ci}`}
                                  onMouseDown={() => handleCellMouseDown(rowNum, ci)}
                                  onMouseEnter={() => handleCellMouseEnter(rowNum, ci)}
                                  title={String(cell ?? '')}
                                  className={`px-2.5 py-1 text-xs whitespace-nowrap transition-colors border-r border-slate-200 min-w-[90px] max-w-[180px] truncate ${
                                    isSelected
                                      ? 'bg-emerald-500/25 text-emerald-950 font-bold border-emerald-400 shadow-inner'
                                      : ri % 2 === 0
                                      ? 'bg-white hover:bg-slate-100 text-slate-900'
                                      : 'bg-slate-50/80 hover:bg-slate-100 text-slate-900'
                                  }`}
                                >
                                  {String(cell ?? '') || '\u00A0'}
                                </td>
                              )
                            })}
                          </tr>
                        )
                      })}
                      {matrixBottomSpacer > 0 && (
                        <tr style={{ height: `${matrixBottomSpacer}px` }} aria-hidden="true">
                          <td colSpan={totalCols + 1} className="p-0 border-0 pointer-events-none" />
                        </tr>
                      )}
                    </tbody>
                  </table>
                ) : (
                  <div className="flex flex-col items-center justify-center py-24 text-slate-500 gap-3">
                    <p className="text-sm font-mono text-slate-600">Chưa tải được bảng tính xem trước</p>
                    <button
                      type="button"
                      onClick={() => selectedFile && fetchFilePreview(selectedFile)}
                      className="px-4 py-2 rounded-xl bg-emerald-500 text-black font-bold text-xs shadow-lg"
                    >
                      Tải lại ma trận bảng tính
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Fullscreen Interactive Matrix Modal */}
            <AnimatePresence>
              {isFullscreen && (
                <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-2 sm:p-4 md:p-6 animate-in fade-in">
                  <motion.div
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.96 }}
                    className="w-full h-full max-w-[98vw] max-h-[96vh] rounded-2xl bg-[#090A0F] border border-emerald-500/50 shadow-[0_0_80px_rgba(16,185,129,0.3)] flex flex-col overflow-hidden"
                  >
                    {/* Fullscreen Header */}
                    <div className="px-5 py-4 bg-[#10141F] border-b border-white/10 flex items-center justify-between flex-wrap gap-3">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                          <TableIcon className="w-5 h-5" />
                        </div>
                        <div>
                          <h3 className="text-base font-bold font-mono text-[#F0F6FC] flex items-center gap-2">
                            <span>Quét tọa độ toàn màn hình:</span>
                            <span className="text-emerald-400">{selectedFile.name}</span>
                          </h3>
                          <p className="text-xs font-mono text-[#94A3B8]">
                            Sheet: {selectedSheet || 'Sheet1'} • {totalDataRows} hàng × {totalCols} cột (Tối đa 1,000,000 dòng)
                          </p>
                        </div>
                      </div>

                      {/* Controls & Close */}
                      <div className="flex items-center gap-3">
                        {/* Horizontal navigation in fullscreen */}
                        <div className="flex items-center bg-[#07090E] border border-white/10 rounded-lg p-0.5 text-xs font-mono">
                          <button
                            type="button"
                            onClick={() => fullscreenScrollRef.current?.scrollTo({ left: 0, behavior: 'smooth' })}
                            title="Về cột A"
                            className="px-2 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-white"
                          >
                            <ChevronsLeft className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => fullscreenScrollRef.current?.scrollBy({ left: -400, behavior: 'smooth' })}
                            className="px-3 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-emerald-400 font-bold flex items-center gap-1"
                          >
                            <ChevronLeft className="w-4 h-4" /> Trái
                          </button>
                          <div className="w-[1px] h-4 bg-white/10 my-auto mx-0.5" />
                          <button
                            type="button"
                            onClick={() => fullscreenScrollRef.current?.scrollBy({ left: 400, behavior: 'smooth' })}
                            className="px-3 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-emerald-400 font-bold flex items-center gap-1"
                          >
                            Phải <ChevronRight className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              if (fullscreenScrollRef.current) {
                                fullscreenScrollRef.current.scrollTo({
                                  left: fullscreenScrollRef.current.scrollWidth,
                                  behavior: 'smooth',
                                })
                              }
                            }}
                            title="Đến cột cuối cùng"
                            className="px-2 py-1 hover:bg-white/10 rounded text-[#94A3B8] hover:text-white"
                          >
                            <ChevronsRight className="w-4 h-4" />
                          </button>
                        </div>

                        {cellRange && (
                          <span className="px-3 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 font-mono font-bold text-xs border border-emerald-500/40 animate-pulse">
                            VÙNG CHỌN: [{cellRange}]
                          </span>
                        )}

                        <button
                          type="button"
                          onClick={() => setIsFullscreen(false)}
                          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white/10 text-[#F0F6FC] hover:bg-white/20 text-xs font-mono font-bold transition-colors"
                        >
                          <Minimize2 className="w-4 h-4" />
                          <span>Thu nhỏ</span>
                        </button>
                      </div>
                    </div>

                    {/* Fullscreen Sub-bar */}
                    <div className="px-5 py-2 bg-[#0C0F17] border-b border-white/5 flex items-center justify-between text-xs font-mono text-[#94A3B8]">
                      <span>💡 <span className="text-emerald-400 font-bold">Kéo rê chuột</span> để quét chọn vùng ô • Nhấp vào tiêu đề cột <code className="text-white">[A], [B]</code> hoặc số dòng <code className="text-white">#</code> để chọn nguyên hàng/cột</span>
                      <span className="text-[#64748B]">Tự động cuộn theo con trỏ chuột khi kéo sát viền</span>
                    </div>

                    {/* Giant Fullscreen Table Container with Virtual 1M-Row Scrolling */}
                    <div
                      ref={fullscreenScrollRef}
                      onScroll={(e) => setFullscreenScrollTop(e.currentTarget.scrollTop)}
                      className="flex-1 overflow-x-auto overflow-y-auto bg-white custom-scrollbar select-none cursor-cell will-change-scroll"
                    >
                      {currentSheetData && currentSheetData.data.length > 0 && (
                        <table className="border-collapse text-xs font-sans table-fixed" style={{ width: 'max-content' }}>
                          <colgroup>
                            <col style={{ width: '48px', minWidth: '48px', maxWidth: '48px' }} />
                            {Array.from({ length: totalCols }).map((_, ci) => {
                              const width = colWidths[ci] || 130
                              return (
                                <col
                                  key={`col-fs-w-${ci}`}
                                  style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                                />
                              )
                            })}
                          </colgroup>
                          <thead className="bg-[#E2E8F0] sticky top-0 z-10 shadow-sm border-b-2 border-slate-300 select-none">
                            <tr>
                              <th className="w-12 px-2.5 py-1.5 text-center text-[11px] font-mono font-bold text-slate-600 bg-[#CBD5E1] border-r border-slate-300 select-none sticky left-0 z-20">
                                #
                              </th>
                              {Array.from({ length: totalCols }).map((_, ci) => {
                                const colLetter = colIndexToLetter(ci)
                                const width = colWidths[ci] || 130
                                return (
                                  <th
                                    key={`th-fs-col-${ci}`}
                                    style={{ width: `${width}px`, minWidth: `${width}px`, maxWidth: `${width}px` }}
                                    onMouseDown={() => handleColHeaderMouseDown(ci)}
                                    onMouseEnter={() => handleColHeaderMouseEnter(ci)}
                                    title={`Kéo hoặc nhấp để chọn Cột [${colLetter}]`}
                                    className="relative px-2.5 py-1.5 text-center text-xs font-mono font-bold text-slate-800 border-r border-slate-300 bg-[#E2E8F0] hover:bg-emerald-100 transition-colors whitespace-nowrap cursor-pointer select-none group overflow-visible"
                                  >
                                    <span className="text-[11px] text-emerald-700 font-mono font-bold bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30">
                                      [{colLetter}]
                                    </span>
                                    {/* Column Resizer Handle */}
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
                          </thead>
                          <tbody className="divide-y divide-slate-200 bg-white">
                            {fsTopSpacer > 0 && (
                              <tr style={{ height: `${fsTopSpacer}px` }} aria-hidden="true">
                                <td colSpan={totalCols + 1} className="p-0 border-0 pointer-events-none" />
                              </tr>
                            )}
                            {fsVisibleRows.map((row, index) => {
                              const ri = fsStartIndex + index
                              const rowNum = ri + 1 // Excel Row number: 1, 2, 3, 4...
                              return (
                                <tr key={`row-${ri}`} className="transition-colors h-[30px]">
                                  <td
                                    onMouseDown={() => handleRowHeaderMouseDown(rowNum)}
                                    onMouseEnter={() => handleRowHeaderMouseEnter(rowNum)}
                                    title={`Kéo hoặc nhấp để chọn Dòng #${rowNum}`}
                                    className="px-2.5 py-1 text-center text-[11px] font-mono font-bold text-slate-500 bg-slate-100 hover:bg-emerald-100 border-r border-slate-300 select-none sticky left-0 z-10 cursor-pointer transition-colors"
                                  >
                                    {rowNum}
                                  </td>
                                  {row.map((cell, ci) => {
                                    const isSelected = isCellSelected(rowNum, ci)
                                    return (
                                      <td
                                        key={`cell-${ri}-${ci}`}
                                        onMouseDown={() => handleCellMouseDown(rowNum, ci)}
                                        onMouseEnter={() => handleCellMouseEnter(rowNum, ci)}
                                        title={String(cell ?? '')}
                                        className={`px-2.5 py-1 text-xs whitespace-nowrap transition-colors border-r border-slate-200 min-w-[90px] max-w-[180px] truncate ${
                                          isSelected
                                            ? 'bg-emerald-500/25 text-emerald-950 font-bold border-emerald-400 shadow-inner'
                                            : ri % 2 === 0
                                            ? 'bg-white hover:bg-slate-100 text-slate-900'
                                            : 'bg-slate-50/80 hover:bg-slate-100 text-slate-900'
                                        }`}
                                      >
                                        {String(cell ?? '') || '\u00A0'}
                                      </td>
                                    )
                                  })}
                                </tr>
                              )
                            })}
                            {fsBottomSpacer > 0 && (
                              <tr style={{ height: `${fsBottomSpacer}px` }} aria-hidden="true">
                                <td colSpan={totalCols + 1} className="p-0 border-0 pointer-events-none" />
                              </tr>
                            )}
                          </tbody>
                        </table>
                      )}
                    </div>

                    {/* Fullscreen Footer Action Bar */}
                    <div className="px-5 py-3.5 bg-[#10141F] border-t border-white/10 flex items-center justify-between flex-wrap gap-3">
                      <div className="flex items-center gap-3">
                        {cellRange ? (
                          <span className="text-xs font-mono text-emerald-400 font-bold">
                            ✓ Đã chọn vùng: [{cellRange}]
                          </span>
                        ) : (
                          <span className="text-xs font-mono text-[#94A3B8]">
                            Chưa chọn vùng cụ thể (Mặc định: Toàn bộ sheet)
                          </span>
                        )}
                        {cellRange && (
                          <button
                            type="button"
                            onClick={() => {
                              setCellRange('')
                              setRangeMode('all')
                            }}
                            className="px-2.5 py-1 rounded bg-red-500/15 text-red-400 text-xs font-mono hover:bg-red-500/25"
                          >
                            Xóa vùng chọn
                          </button>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => setIsFullscreen(false)}
                          className="px-5 py-2.5 rounded-xl bg-emerald-500 text-black font-bold font-mono text-xs hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all"
                        >
                          ✓ XÁC NHẬN VÙNG CHỌN & ĐÓNG
                        </button>
                      </div>
                    </div>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Conversion Options Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Output Format */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#B8E900]" /> 1. ĐÍCH CHUYỂN ĐỔI
                </label>
                <div className={`grid ${availableSpreadsheetFormats.length === 2 ? 'grid-cols-2' : 'grid-cols-3'} gap-1.5`}>
                  {availableSpreadsheetFormats.map((fmt) => {
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

              {/* CSV Delimiter Settings */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-[#B8E900]" /> 2. PHÂN CÁCH (DELIMITER)
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { val: ',', label: 'Phẩy (,)' },
                    { val: ';', label: 'Chấm (;)' },
                    { val: '\t', label: 'Tab (\\t)' },
                  ].map((d) => {
                    const isSelected = delimiter === d.val
                    return (
                      <button
                        key={d.val}
                        type="button"
                        onClick={() => setDelimiter(d.val as any)}
                        className={`py-2 px-1 rounded-xl text-xs font-tech font-bold uppercase transition-all text-center ${
                          isSelected
                            ? 'bg-[#222530] border border-[#B8E900] text-white'
                            : 'bg-[#222530] border border-[#2E313E] text-[#9CA3AF] hover:text-white'
                        }`}
                      >
                        {d.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* JSON & Header Options */}
              <div className="p-3.5 rounded-xl bg-[#181A22] border border-[#282B37] space-y-2.5">
                <label className="text-xs font-tech font-bold uppercase text-white">3. CẤU HÌNH BỔ SUNG</label>
                
                {/* Header Toggle Card */}
                <button
                  type="button"
                  onClick={() => setIncludeHeader(!includeHeader)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-tech font-bold uppercase transition-all border text-left ${
                    includeHeader
                      ? 'bg-[#222530] border border-[#B8E900] text-white'
                      : 'bg-[#222530] border border-[#2E313E] text-[#9CA3AF] hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className={`w-3.5 h-3.5 flex-shrink-0 ${includeHeader ? 'text-[#B8E900]' : 'text-[#6B7280]'}`} />
                    <span className="truncate">Dòng tiêu đề</span>
                  </div>
                  <div
                    className={`w-4 h-4 rounded flex items-center justify-center transition-all flex-shrink-0 ml-1.5 ${
                      includeHeader
                        ? 'bg-[#B8E900] text-[#0C0D10]'
                        : 'bg-[#181A22] border border-white/20 text-transparent'
                    }`}
                  >
                    <Check className="w-3 h-3 stroke-[3]" />
                  </div>
                </button>

                <div className="flex items-center justify-between text-xs text-[#9CA3AF]">
                  <span className="font-mono text-[11px]">JSON Indent:</span>
                  <div className="flex gap-1.5">
                    {[2, 4].map((ind) => (
                      <button
                        key={ind}
                        type="button"
                        onClick={() => setIndent(ind as any)}
                        className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold transition-all ${
                          indent === ind
                            ? 'bg-[#B8E900] text-[#0C0D10]'
                            : 'bg-[#222530] text-[#9CA3AF] hover:text-white border border-[#2E313E]'
                        }`}
                      >
                        {ind} sp
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Action Button */}
            <div className="pt-2">
              <Button
                variant="primary"
                size="lg"
                onClick={handleConvert}
                isLoading={isProcessing}
                className="w-full py-3.5 sm:py-4 text-sm font-black"
              >
                <Zap className="w-4 h-4 mr-1.5" />
                {isProcessing
                  ? 'ĐANG XỬ LÝ MA TRẬN DỮ LIỆU...'
                  : getComputedRange()
                  ? `TIẾN HÀNH XUẤT VÙNG Ô [${getComputedRange()}] NGAY`
                  : 'TIẾN HÀNH CHUYỂN ĐỔI BẢNG TÍNH NGAY'}
              </Button>
              <p className="text-center text-[10px] font-mono text-[#6B7280] mt-2">
                Đảm bảo dữ liệu chuẩn xác, tự động gắn UTF-8 BOM chống lỗi font tiếng Việt trên Microsoft Excel
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}

