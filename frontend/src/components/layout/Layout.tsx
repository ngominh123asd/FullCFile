import { useState, useEffect } from 'react'
import { Outlet, useLocation, Link, useNavigate } from 'react-router-dom'
import {
  Layers,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Globe,
  User as UserIcon,
  LogOut,
  Menu,
  X,
  Zap,
  ArrowLeft,
  FileText,
  Table as TableIcon,
} from 'lucide-react'
import { useI18n } from '../../lib/i18n'
import { systemApi } from '../../lib/api'
import { useAuthStore } from '../../lib/auth'
import { clsx } from 'clsx'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)
  const [isBackendOnline, setIsBackendOnline] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, isAuthenticated, logout } = useAuthStore()
  const { lang, setLang } = useI18n()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { icon: Layers, label: 'Bàn Làm Việc', sub: 'NORMALIZER', path: '/dashboard', code: '01' },
    { icon: History, label: 'Nhật Ký Tác Vụ', sub: 'LOGS', path: '/dashboard/history', code: '02' },
    { icon: Settings, label: 'Cài Đặt Hệ Thống', sub: 'CONFIG', path: '/dashboard/settings', code: '03' },
  ]

  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false)
    }
  }, [location.pathname])

  useEffect(() => {
    const check = async () => {
      const res = await systemApi.checkHealth()
      setIsBackendOnline(res.online)
    }
    check()
    const timer = setInterval(check, 15000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="min-h-screen zzz-carbon-bg flex text-[#F8FAFC] antialiased relative">
      {/* Mobile Dark Backdrop when Sidebar is Open */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-30 md:hidden transition-opacity"
        />
      )}

      {/* ZZZ .FUNCTIONS Hardware Device Sidebar (Screenshot 1) */}
      <aside
        className={clsx(
          'fixed left-0 top-0 h-full bg-[#181A22] border-r-2 border-[#282B37] z-40 flex flex-col select-none shadow-[8px_0_30px_rgba(0,0,0,0.8)] transition-all duration-200 ease-out overflow-hidden',
          sidebarOpen
            ? 'w-[280px] translate-x-0'
            : 'w-[84px] -translate-x-full md:translate-x-0'
        )}
      >
        {/* Device Top Embossed Header (Screenshot 1: .FUNCTIONS) */}
        <div className="p-4 border-b border-[#282B37] bg-[#14151C] flex items-center justify-between relative">
          <Link to="/" className="flex items-center gap-3 group">
            {/* Hanging Charm Slot + Logo */}
            <div className="w-9 h-9 rounded-xl bg-[#242733] border border-[#353846] text-[#B8E900] flex items-center justify-center font-black text-lg shadow-sm flex-shrink-0 group-hover:scale-105 transition-transform">
              Z
            </div>
            {sidebarOpen && (
              <div className="truncate">
                <div className="flex items-center gap-1.5">
                  <span className="font-tech font-black text-sm tracking-wider text-white">
                    .FUNCTIONS
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#9CA3AF]">
                  <span className={clsx("w-1.5 h-1.5 rounded-full", isBackendOnline ? "bg-[#B8E900]" : "bg-[#FF5E00]")} />
                  <span>ONLINE // REV.2.4</span>
                </div>
              </div>
            )}
          </Link>

          {/* Mobile Close Button */}
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-1.5 rounded-lg text-[#9CA3AF] hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Section Header: FREQUENT (Screenshot 1) */}
        <div className="px-4 pt-3 pb-1 text-[10px] font-mono text-[#6B7280] uppercase tracking-wider flex items-center justify-between">
          <span>FREQUENT</span>
          <span className="text-[#B8E900] font-bold">MODE 01</span>
        </div>

        {/* Navigation Grid Tiles (Screenshot 1: 24h, Cửa Hàng, Kho...) */}
        <nav className="flex-1 p-3 space-y-2.5 overflow-y-auto custom-scrollbar">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                className={clsx(
                  'flex items-center gap-3.5 px-3 py-2.5 rounded-xl transition-all group relative',
                  isActive
                    ? 'bg-[#2B2E3C] border border-[#B8E900] shadow-[0_0_12px_rgba(184,233,0,0.2)]'
                    : 'bg-[#222530] border border-[#2D303E] hover:border-[#4A5064] hover:bg-[#282B37]'
                )}
              >
                {/* Tile Icon Square */}
                <div className={clsx(
                  'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors',
                  isActive ? 'bg-[#B8E900] text-[#0C0D10]' : 'bg-[#181A22] text-white'
                )}>
                  <Icon className="w-4 h-4 stroke-[2.5]" />
                </div>

                {sidebarOpen && (
                  <div className="truncate text-left">
                    <p className={clsx('text-xs font-tech font-bold uppercase tracking-wider truncate', isActive ? 'text-white' : 'text-[#D1D5DB]')}>
                      {item.label}
                    </p>
                    <p className="text-[10px] font-mono text-[#6B7280]">
                      {item.sub}
                    </p>
                  </div>
                )}

                {isActive && (
                  <div className="absolute right-3 w-2 h-2 rounded-full bg-[#B8E900]" />
                )}
              </Link>
            )
          })}

          {/* Quick Engine Spec Badges */}
          {sidebarOpen && (
            <div className="pt-4 border-t border-[#262834] space-y-2">
              <div className="px-1 text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
                COMMUNITY &amp; TOOLS
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-[#222530] border border-[#2D303E] text-center">
                  <FileText className="w-4 h-4 text-white mx-auto mb-1" />
                  <span className="text-[10px] font-mono font-bold text-white block">DOCS</span>
                  <span className="text-[9px] font-mono text-[#6B7280]">PANDOC</span>
                </div>
                <div className="p-2.5 rounded-xl bg-[#222530] border border-[#2D303E] text-center">
                  <TableIcon className="w-4 h-4 text-white mx-auto mb-1" />
                  <span className="text-[10px] font-mono font-bold text-white block">MATRIX</span>
                  <span className="text-[9px] font-mono text-[#6B7280]">LIBRE</span>
                </div>
              </div>
            </div>
          )}
        </nav>

        {/* Sidebar Footer Controls */}
        <div className="p-3 border-t border-[#282B37] flex items-center justify-between gap-2 bg-[#14151C]">
          <Link
            to="/"
            className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-[#222530] border border-[#2D303E] hover:border-white text-xs font-tech font-bold uppercase text-[#9CA3AF] hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {sidebarOpen && <span>VỀ TRANG CHỦ</span>}
          </Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="hidden md:flex p-2 rounded-xl bg-[#222530] border border-[#2D303E] text-[#9CA3AF] hover:text-white transition-colors cursor-pointer"
            title={sidebarOpen ? "Thu gọn" : "Mở rộng"}
          >
            {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </aside>

      {/* Main Workstation Stage */}
      <main
        className={clsx(
          'flex-1 min-h-screen flex flex-col zzz-carbon-bg transition-[margin-left] duration-200 ease-out min-w-0 max-w-full overflow-x-hidden relative',
          sidebarOpen ? 'md:ml-[280px] ml-0' : 'md:ml-[84px] ml-0'
        )}
      >
        {/* Top ZZZ In-Game Navigation Bar (Screenshot 1 & 3) */}
        <header className="sticky top-0 z-20 bg-[#14151C]/90 backdrop-blur-md border-b border-[#282B37] px-4 sm:px-6 py-2.5 flex items-center justify-between w-full max-w-full overflow-hidden shadow-sm">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Menu Trigger */}
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-2 rounded-xl bg-[#222530] text-white border border-[#323646]"
              title="Mở menu"
            >
              <Menu className="w-4 h-4" />
            </button>

            {/* Back Capsule Button (Screenshot 1 & 2: Black pill with red arrow) */}
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="hidden sm:flex items-center justify-center w-8 h-8 rounded-full bg-[#181A22] border border-[#2C2F3D] text-[#FF3355] hover:bg-[#222530] transition-colors"
              title="Quay lại"
            >
              <ArrowLeft className="w-4 h-4 stroke-[2.5]" />
            </button>

            {/* ZZZ Top Pill Capsule Bar (Screenshot 1: Chủ Đề / Mặt Dây) */}
            <div className="zzz-pill-container">
              <Link
                to="/dashboard"
                className={location.pathname === '/dashboard' ? 'zzz-pill-active' : 'zzz-pill-inactive'}
              >
                Chuyển Đổi
              </Link>
              <Link
                to="/dashboard/history"
                className={location.pathname === '/dashboard/history' ? 'zzz-pill-active' : 'zzz-pill-inactive'}
              >
                Nhật Ký
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
            {/* Battery Power Cell (Screenshot 3 style) */}
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#181A22] border border-[#2E313E] text-xs font-mono text-[#D1D5DB]">
              <Zap className="w-3.5 h-3.5 text-[#B8E900] fill-[#B8E900]" />
              <span className="text-[11px] font-bold">240/240</span>
            </div>

            {/* Language Switcher */}
            <button
              onClick={() => setLang(lang === 'vi' ? 'en' : 'vi')}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono bg-[#181A22] border border-[#2E313E] text-[#9CA3AF] hover:text-white transition-colors"
            >
              <Globe className="w-3.5 h-3.5" />
              <span className="font-tech font-bold text-[11px]">{lang === 'vi' ? 'VI' : 'EN'}</span>
            </button>

            {/* User Profile */}
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2 pl-2 border-l border-[#282B37]">
                <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#181A22] border border-[#2E313E] text-xs font-mono">
                  <div className="w-4 h-4 rounded-full bg-[#B8E900] text-[#0C0D10] flex items-center justify-center font-black text-[9px] flex-shrink-0">
                    {user.name ? user.name[0].toUpperCase() : 'P'}
                  </div>
                  <span className="font-bold text-white max-w-[100px] truncate hidden sm:inline">
                    {user.name || user.email.split('@')[0]}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Đăng xuất"
                  className="p-1.5 rounded-full bg-[#181A22] border border-[#2E313E] text-[#9CA3AF] hover:text-[#FF3355] transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="btn-zzz-primary text-xs px-3.5 py-1 flex items-center gap-1.5 rounded-full"
              >
                <UserIcon className="w-3.5 h-3.5" />
                <span>ĐĂNG NHẬP</span>
              </button>
            )}
          </div>
        </header>

        {/* Workstation Outlet Container */}
        <div className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto min-w-0 overflow-x-hidden relative z-10">
          <Outlet />
        </div>

        {/* ZZZ Minimal Footer */}
        <footer className="mt-auto px-6 py-3 border-t border-[#20222C] bg-[#101116] text-[11px] font-mono text-[#6B7280] flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-[#9CA3AF]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
            <span>FILEFORGE // PROXY FUNCTIONS</span>
          </div>
          <div className="flex items-center gap-3">
            <span>ZERO-RETENTION LOCAL STORAGE</span>
            <span className="text-white">REV. 2.4</span>
          </div>
        </footer>
      </main>
    </div>
  )
}
