export type SupportedFormat = 
  | 'docx' | 'pdf' | 'html' | 'md' | 'txt' | 'rtf'
  | 'xlsx' | 'csv' | 'json' | 'ods'
  | 'png' | 'jpg' | 'jpeg' | 'tiff' | 'bmp' | 'webp'

export type FileCategory = 'document' | 'ocr' | 'spreadsheet' | 'archive'

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface UploadedFile {
  id: string
  filename: string
  original_filename: string
  file_type: string
  file_size: number
  content_type?: string
  created_at?: string
  expires_at?: string
  url?: string
}

export interface Job {
  id: string
  user_id: string
  input_file_id: string
  input_filename?: string
  job_type: 'convert' | 'ocr' | 'spreadsheet'
  status: JobStatus
  output_format: string
  progress: number
  stage?: string
  error?: string
  result?: {
    output_path?: string
    text?: string
    stats?: Record<string, any>
    detected_language?: string
    confidence?: number
    [key: string]: any
  }
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface OcrOptions {
  engine?: 'fast_native' | 'vietocr'
  language?: 'auto' | 'vi' | 'en' | 'ch' | 'ja'
  preserve_layout?: boolean
  preserve_tables?: boolean
  enhance?: boolean
  use_gpu?: boolean
  det_thresh?: number
  det_box_thresh?: number
  det_unclip_ratio?: number
  rec_score_thresh?: number
  cls_thresh?: number
  max_side_len?: number
  det_model_path?: string
  rec_model_path?: string
}

export interface SpreadsheetOptions {
  sheet_name?: string
  cell_range?: string
  start_row?: number
  end_row?: number
  start_col?: string
  end_col?: string
  delimiter?: string
  include_header?: boolean
  indent?: number
}

export interface ConvertOptions {
  template?: 'modern' | 'academic' | 'executive' | 'minimal'
  toc?: boolean
  page_numbers?: boolean
}

export interface PreviewData {
  job_id: string
  format: string
  previewable: boolean
  content?: string
  paragraphs?: string[]
  tables?: string[][][]
  sheets?: Array<{
    name: string
    data: (string | number | null)[][]
    total_rows?: number
    total_cols?: number
  }>
  sheet_names?: string[]
  url?: string
  file_size?: number
  render_type?: string
  error?: string
}

export type AppLanguage = 'vi' | 'en'
