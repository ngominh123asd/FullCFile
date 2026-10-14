import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import HeroTransformationConsole from '../components/features/HeroTransformationConsole'
import ArchitecturalBackground from '../components/layout/ArchitecturalBackground'
import {
  FileText,
  Image as ImageIcon,
  Table as TableIcon,
  Zap,
  ArrowRight,
  Cpu,
  ChevronDown,
  Globe,
  Check,
  ShieldCheck,
  Activity,
  Gauge,
  Sparkles,
} from 'lucide-react'
import LiveSandbox from '../components/features/LiveSandbox'
import ApiPlayground from '../components/features/ApiPlayground'
import { useI18n } from '../lib/i18n'

export default function LandingPage() {
  const navigate = useNavigate()
  const { lang, setLang, t } = useI18n()
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  const toggleFaq = (index: number) => {
    setOpenFaq(openFaq === index ? null : index)
  }

  return (
    <div className="min-h-screen zzz-carbon-bg text-[#F8FAFC] antialiased relative selection:bg-[#B8E900] selection:text-[#0C0D10]">
      {/* ZZZ In-Game Carbon Weave & Filmstrip Watermark */}
      <ArchitecturalBackground />

      {/* Floating ZZZ Top Navigation Bar (Screenshot 1 & 3) */}
      <nav className="sticky top-0 z-40 bg-[#14151C]/90 backdrop-blur-md border-b border-[#282B37] shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 sm:h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3 cursor-pointer min-w-0" onClick={() => navigate('/')}>
            <div className="w-8 h-8 rounded-xl bg-[#242733] border border-[#353846] text-[#B8E900] flex items-center justify-center font-black text-lg shadow-sm flex-shrink-0">
              Z
            </div>
            <div className="flex items-center gap-2 truncate">
              <span className="font-tech font-bold text-base sm:text-lg tracking-wider text-white truncate">
                .FUNCTIONS
              </span>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#222530] text-[#9CA3AF] border border-[#2E313E] flex-shrink-0">
                REV. 2.4
              </span>
            </div>
          </div>

          {/* Links */}
          <div className="hidden md:flex items-center gap-6 text-xs font-tech font-bold tracking-wider">
            <a href="#sandbox" className="text-[#9CA3AF] hover:text-white transition-colors">
              [ SANDBOX ]
            </a>
            <a href="#features" className="text-[#9CA3AF] hover:text-white transition-colors">
              [ TÍNH NĂNG ]
            </a>
            <a href="#api" className="text-[#9CA3AF] hover:text-white transition-colors">
              [ REST API ]
            </a>
            <a href="#pricing" className="text-[#9CA3AF] hover:text-white transition-colors">
              [ BẢNG GIÁ ]
            </a>
          </div>

          {/* Action & Language Toggle */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <button
              onClick={() => setLang(lang === 'vi' ? 'en' : 'vi')}
              className="flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded-full bg-[#181A22] border border-[#282B37] text-[#9CA3AF] hover:text-white transition-all"
            >
              <Globe className="w-3.5 h-3.5" />
              <span>{lang === 'vi' ? 'VI' : 'EN'}</span>
            </button>

            <button
              onClick={() => navigate('/login')}
              className="hidden sm:inline-flex btn-zzz-dark px-3.5 py-1.5 text-xs font-tech font-bold uppercase transition-all rounded-full"
            >
              <span>ĐĂNG NHẬP</span>
            </button>

            <button
              onClick={() => navigate('/register')}
              className="btn-zzz-primary text-xs px-4 py-1.5 flex items-center gap-1 font-tech font-black uppercase rounded-full"
            >
              <Zap className="w-3.5 h-3.5 stroke-[2.5]" />
              <span className="hidden sm:inline">BẮT ĐẦU NGAY</span>
              <span className="sm:hidden">KHỞI ĐỘNG</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 pt-10 sm:pt-14 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Left Column: Brand Identity & Telemetry Stats */}
          <div className="lg:col-span-6 space-y-6 text-left">
            {/* Top Pill Beacon */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#181A22] border border-[#2E313E] text-xs font-tech font-bold uppercase tracking-wider text-white"
            >
              <span className="w-2 h-2 rounded-full bg-[#B8E900]" />
              <span>{t('hero.badge')}</span>
            </motion.div>

            {/* Main Heading */}
            <motion.h1
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-3xl sm:text-4xl lg:text-5xl font-black font-tech tracking-wider leading-[1.18] text-white uppercase"
            >
              {t('hero.title_1')}{' '}
              <span className="text-white underline decoration-2 decoration-[#B8E900]">
                {t('hero.title_2')}
              </span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-sm sm:text-base text-[#9CA3AF] font-mono leading-relaxed"
            >
              {t('hero.desc')}
            </motion.p>

            {/* 3 Real-time Hardware Metrics Cards (Screenshot 1: Tiles) */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="grid grid-cols-3 gap-2.5 pt-1"
            >
              {/* Card 1: Speed */}
              <div className="p-3.5 rounded-2xl bg-[#181A22] border border-[#2C2F3D] shadow-sm relative overflow-hidden group">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5 text-white text-xs font-tech font-bold uppercase">
                    <Gauge className="w-3.5 h-3.5" />
                    <span>TỐC ĐỘ</span>
                  </div>
                  <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
                </div>
                <div className="text-base sm:text-lg font-mono font-bold text-white">
                  {t('hero.metric_speed')}
                </div>
                <p className="text-[10px] text-[#9CA3AF] font-mono mt-0.5 leading-tight">
                  {t('hero.metric_speed_label')}
                </p>
              </div>

              {/* Card 2: Accuracy */}
              <div className="p-3.5 rounded-2xl bg-[#181A22] border border-[#2C2F3D] shadow-sm relative overflow-hidden group">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5 text-white text-xs font-tech font-bold uppercase">
                    <Activity className="w-3.5 h-3.5" />
                    <span>ĐỘ CHUẨN</span>
                  </div>
                  <span className="w-1.5 h-1.5 rounded-full bg-white" />
                </div>
                <div className="text-base sm:text-lg font-mono font-bold text-white">
                  {t('hero.metric_accuracy')}
                </div>
                <p className="text-[10px] text-[#9CA3AF] font-mono mt-0.5 leading-tight">
                  {t('hero.metric_accuracy_label')}
                </p>
              </div>

              {/* Card 3: Privacy */}
              <div className="p-3.5 rounded-2xl bg-[#181A22] border border-[#2C2F3D] shadow-sm relative overflow-hidden group">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5 text-white text-xs font-tech font-bold uppercase">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>BẢO MẬT</span>
                  </div>
                  <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
                </div>
                <div className="text-base sm:text-lg font-mono font-bold text-white">
                  {t('hero.metric_privacy')}
                </div>
                <p className="text-[10px] text-[#9CA3AF] font-mono mt-0.5 leading-tight">
                  {t('hero.metric_privacy_label')}
                </p>
              </div>
            </motion.div>

            {/* Action CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2"
            >
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="btn-zzz-primary py-3.5 px-6 text-xs sm:text-sm flex items-center justify-center gap-2 rounded-xl"
              >
                <Zap className="w-4 h-4 fill-[#0C0D10] stroke-[#0C0D10]" />
                <span>{t('hero.cta_start')}</span>
                <ArrowRight className="w-4 h-4 ml-1 stroke-[3]" />
              </button>

              <button
                type="button"
                onClick={() => {
                  document.getElementById('sandbox')?.scrollIntoView({ behavior: 'smooth' })
                }}
                className="btn-zzz-dark py-3.5 px-6 text-xs sm:text-sm flex items-center justify-center gap-2 rounded-xl"
              >
                <Sparkles className="w-4 h-4 text-white" />
                <span>{t('hero.cta_demo')}</span>
              </button>
            </motion.div>
          </div>

          {/* Right Column: Hero Transformation Console */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="lg:col-span-6"
          >
            <HeroTransformationConsole />
          </motion.div>
        </div>
      </section>

      {/* Interactive Live Sandbox Section */}
      <section id="sandbox" className="relative z-10 py-16 px-6 bg-[#14151C] border-y border-[#262936]">
        <div className="max-w-6xl mx-auto">
          <LiveSandbox />
        </div>
      </section>

      {/* Bento Grid Features (Screenshot 1: Tiles) */}
      <section id="features" className="relative z-10 py-24 px-6">
        <div className="max-w-6xl mx-auto space-y-16">
          <div className="text-center space-y-3">
            <span className="text-xs font-mono text-[#9CA3AF] uppercase tracking-widest font-bold">
              ENGINE SPECIFICATIONS
            </span>
            <h2 className="text-3xl md:text-5xl font-bold font-tech text-white">
              {t('features.title')}
            </h2>
            <p className="text-sm text-[#9CA3AF] max-w-2xl mx-auto">{t('features.subtitle')}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Feature 1: OCR */}
            <div className="zzz-device-frame p-8 space-y-4">
              <div className="w-12 h-12 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white">
                <ImageIcon className="w-6 h-6 stroke-[2]" />
              </div>
              <h3 className="text-xl font-bold font-tech text-white uppercase">{t('features.ocr_title')}</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">{t('features.ocr_desc')}</p>
              <div className="pt-2 flex flex-wrap gap-2 text-xs font-mono text-white">
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">PP-Structure v2.8</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Auto Rotation</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Table Reconstruction</span>
              </div>
            </div>

            {/* Feature 2: Doc Normalizer */}
            <div className="zzz-device-frame p-8 space-y-4">
              <div className="w-12 h-12 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white">
                <FileText className="w-6 h-6 stroke-[2]" />
              </div>
              <h3 className="text-xl font-bold font-tech text-white uppercase">{t('features.doc_title')}</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">{t('features.doc_desc')}</p>
              <div className="pt-2 flex flex-wrap gap-2 text-xs font-mono text-white">
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Markdown ➔ DOCX</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">LibreOffice Engine</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Academic Styles</span>
              </div>
            </div>

            {/* Feature 3: Spreadsheet Matrix */}
            <div className="zzz-device-frame p-8 space-y-4">
              <div className="w-12 h-12 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white">
                <TableIcon className="w-6 h-6 stroke-[2]" />
              </div>
              <h3 className="text-xl font-bold font-tech text-white uppercase">{t('features.sheet_title')}</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">{t('features.sheet_desc')}</p>
              <div className="pt-2 flex flex-wrap gap-2 text-xs font-mono text-white">
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">XLSX ➔ JSON</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">CSV Detector</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Multi-sheet Support</span>
              </div>
            </div>

            {/* Feature 4: Async Pipeline */}
            <div className="zzz-device-frame p-8 space-y-4">
              <div className="w-12 h-12 rounded-xl bg-[#222530] border border-[#323646] flex items-center justify-center text-white">
                <Cpu className="w-6 h-6 stroke-[2]" />
              </div>
              <h3 className="text-xl font-bold font-tech text-white uppercase">{t('features.queue_title')}</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">{t('features.queue_desc')}</p>
              <div className="pt-2 flex flex-wrap gap-2 text-xs font-mono text-white">
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Redis Queue</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Celery Workers</span>
                <span className="px-2.5 py-1 rounded-lg bg-[#222530] border border-[#2E313E]">Realtime Stream</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Developer API Playground Section */}
      <section id="api" className="relative z-10 py-16 px-6 bg-[#14151C] border-t border-[#262936]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="text-center space-y-2">
            <span className="text-xs font-mono text-[#9CA3AF] uppercase tracking-widest font-bold">
              DEVELOPER INTEGRATION
            </span>
            <h2 className="text-3xl font-bold font-tech text-white">
              Tích Hợp API Vào Dự Án
            </h2>
            <p className="text-xs sm:text-sm text-[#9CA3AF]">
              RESTful endpoints công khai, hỗ trợ gửi payload đa định dạng với phản hồi JSON tiêu chuẩn.
            </p>
          </div>

          <ApiPlayground />
        </div>
      </section>

      {/* Pricing Matrix */}
      <section id="pricing" className="relative z-10 py-24 px-6">
        <div className="max-w-6xl mx-auto space-y-12">
          <div className="text-center space-y-2">
            <span className="text-xs font-mono text-[#9CA3AF] uppercase tracking-widest font-bold">TRANSPARENT TIERS</span>
            <h2 className="text-3xl md:text-5xl font-bold font-tech text-white">Bảng Giá Mở &amp; Linh Hoạt</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Free Tier */}
            <div className="zzz-device-frame p-8 flex flex-col justify-between space-y-6">
              <div className="space-y-4">
                <span className="px-3 py-1 rounded-full text-xs font-mono bg-[#222530] text-[#9CA3AF] border border-[#2E313E]">COMMUNITY</span>
                <h3 className="text-2xl font-bold font-tech text-white">Miễn Phí</h3>
                <p className="text-3xl font-mono font-bold text-white">0đ <span className="text-xs font-normal text-[#9CA3AF]">/ tháng</span></p>
                <ul className="space-y-2.5 text-xs text-[#9CA3AF] pt-4 border-t border-[#282B37]">
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> 100 tác vụ chuyển đổi / ngày</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> PaddleOCR tiếng Việt &amp; Anh</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Kích thước file lên đến 100MB</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Không cần đăng ký tài khoản</li>
                </ul>
              </div>
              <button onClick={() => navigate('/dashboard')} className="btn-zzz-dark w-full py-2.5 text-xs font-tech font-bold uppercase rounded-xl">
                Sử Dụng Ngay
              </button>
            </div>

            {/* Pro Tier (Featured) */}
            <div className="zzz-device-frame p-8 border border-[#B8E900]/70 flex flex-col justify-between space-y-6 relative shadow-[0_0_20px_rgba(184,233,0,0.15)]">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-[#B8E900] text-[#0C0D10] text-[10px] font-mono font-bold uppercase">
                RECOMMENDED
              </div>
              <div className="space-y-4">
                <span className="px-3 py-1 rounded-full text-xs font-mono bg-[#222530] text-white border border-[#2E313E]">DEVELOPER PRO</span>
                <h3 className="text-2xl font-bold font-tech text-white">Chuyên Nghiệp</h3>
                <p className="text-3xl font-mono font-bold text-white">199,000đ <span className="text-xs font-normal text-[#9CA3AF]">/ tháng</span></p>
                <ul className="space-y-2.5 text-xs text-white pt-4 border-t border-[#282B37]">
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Không giới hạn lượt chuyển đổi</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Ưu tiên hàng đợi tốc độ cao</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Hỗ trợ API Key không giới hạn rate limit</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> File lên tới 500MB</li>
                </ul>
              </div>
              <button onClick={() => navigate('/dashboard')} className="btn-zzz-primary w-full py-3 text-xs font-tech font-black uppercase rounded-xl">
                Dùng Thử Miễn Phí
              </button>
            </div>

            {/* Enterprise Tier */}
            <div className="zzz-device-frame p-8 flex flex-col justify-between space-y-6">
              <div className="space-y-4">
                <span className="px-3 py-1 rounded-full text-xs font-mono bg-[#222530] text-[#9CA3AF] border border-[#2E313E]">ENTERPRISE</span>
                <h3 className="text-2xl font-bold font-tech text-white">Tự Triển Khai</h3>
                <p className="text-3xl font-mono font-bold text-white">Liên hệ</p>
                <ul className="space-y-2.5 text-xs text-[#9CA3AF] pt-4 border-t border-[#282B37]">
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Docker Compose On-Premise</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Mô hình OCR tùy chỉnh chuyên sâu</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Cam kết SLA 99.99%</li>
                  <li className="flex items-center gap-2"><Check className="w-4 h-4 text-[#B8E900]" /> Hỗ trợ kỹ thuật 24/7</li>
                </ul>
              </div>
              <button onClick={() => navigate('/dashboard')} className="btn-zzz-dark w-full py-2.5 text-xs font-tech font-bold uppercase rounded-xl">
                Tư Vấn Doanh Nghiệp
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="relative z-10 py-16 px-6 bg-[#14151C] border-t border-[#262936]">
        <div className="max-w-4xl mx-auto space-y-8">
          <div className="text-center space-y-2">
            <span className="text-xs font-mono text-[#9CA3AF] font-bold">HỎI &amp; ĐÁP</span>
            <h2 className="text-3xl font-bold font-tech text-white">Câu Hỏi Thường Gặp</h2>
          </div>

          <div className="space-y-3">
            {[
              {
                q: 'FileForge có lưu trữ tài liệu nhạy cảm của tôi không?',
                a: 'Tập tin tải lên sẽ được tự động dọn dẹp sau 24 giờ. Hệ thống không lưu trữ hoặc sử dụng dữ liệu của bạn để huấn luyện mô hình bên ngoài.',
              },
              {
                q: 'Khả năng nhận diện tiếng Việt của OCR có hỗ trợ chữ viết tay không?',
                a: 'PaddleOCR PP-Structure hỗ trợ tốt nhất cho văn bản in, hóa đơn, tài liệu scan và ảnh chụp văn bản rõ nét có dấu.',
              },
              {
                q: 'Làm thế nào để chạy hệ thống trên máy chủ riêng (Self-hosted)?',
                a: 'Bạn có thể khởi chạy bằng Docker Compose có sẵn trong repository thông qua lệnh `docker-compose up -d`.',
              },
            ].map((faq, idx) => (
              <div
                key={idx}
                className="p-5 rounded-2xl bg-[#181A22] border border-[#282B37] cursor-pointer hover:border-[#383C4C] transition-colors"
                onClick={() => toggleFaq(idx)}
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-white font-tech uppercase">{faq.q}</h4>
                  <ChevronDown
                    className={`w-4 h-4 text-[#9CA3AF] transition-transform ${
                      openFaq === idx ? 'rotate-180 text-white' : ''
                    }`}
                  />
                </div>
                {openFaq === idx && (
                  <p className="text-xs text-[#9CA3AF] mt-3 pt-3 border-t border-[#242734] leading-relaxed font-mono">
                    {faq.a}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ZZZ Minimal Footer */}
      <footer className="relative z-10 border-t border-[#282B37] py-10 px-6 bg-[#101116]">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-[#222530] text-[#B8E900] flex items-center justify-center font-bold text-sm border border-[#323646]">
              Z
            </div>
            <span className="text-sm font-mono font-bold text-white">
              .FUNCTIONS // FILEFORGE • 2026
            </span>
          </div>

          <p className="text-xs font-mono text-[#9CA3AF]">
            Document &amp; Data Intelligence Studio. Powered by PaddleOCR &amp; FastAPI.
          </p>

          <div className="flex items-center gap-4 text-xs font-mono text-[#9CA3AF]">
            <a href="/docs" target="_blank" className="hover:text-white transition-colors">
              API Docs
            </a>
            <span>•</span>
            <span className="text-white flex items-center gap-1.5 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" /> All Systems Online
            </span>
          </div>
        </div>
      </footer>
    </div>
  )
}
