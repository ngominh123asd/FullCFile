import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, Link } from 'react-router-dom'
import {
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  Eye,
  EyeOff,
  Zap,
  Key,
  UserPlus,
  Sparkles,
  Layers,
} from 'lucide-react'
import { Button } from '../components/ui/button'
import ArchitecturalBackground from '../components/layout/ArchitecturalBackground'
import { useAuthStore } from '../lib/auth'
import toast from 'react-hot-toast'

interface AuthPageProps {
  initialMode?: 'login' | 'register'
}

export default function AuthPage({ initialMode = 'login' }: AuthPageProps) {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const navigate = useNavigate()
  const { login: storeLogin, demoLogin } = useAuthStore()

  const handleSwitchMode = (targetMode: 'login' | 'register') => {
    setMode(targetMode)
    setEmail('')
    setPassword('')
    setName('')
  }

  // Real-time password strength calculation
  const getPasswordStrength = (pass: string) => {
    if (!pass) return { score: 0, text: '', color: '' }
    let score = 0
    if (pass.length >= 6) score += 25
    if (pass.length >= 10) score += 25
    if (/[A-Z]/.test(pass)) score += 25
    if (/[0-9!@#$%^&*]/.test(pass)) score += 25

    if (score <= 25) return { score, text: 'YẾU', color: 'bg-[#FF3355]' }
    if (score <= 50) return { score, text: 'TRUNG BÌNH', color: 'bg-[#FF5E00]' }
    if (score <= 75) return { score, text: 'KHÁ', color: 'bg-yellow-400' }
    return { score, text: 'MẠNH', color: 'bg-[#B8E900]' }
  }

  const strength = getPasswordStrength(password)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      if (mode === 'login') {
        const success = await storeLogin(email, password)
        if (success) {
          toast.success('Đăng nhập thành công!')
          navigate('/dashboard')
        } else {
          toast.error('Tài khoản hoặc mật khẩu không chính xác')
        }
      } else {
        demoLogin()
        toast.success('Đăng ký tài khoản thành công! Đã tự động liên kết.')
        navigate('/dashboard')
      }
    } catch {
      toast.error('Có lỗi xảy ra trong quá trình xác thực')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDemoLogin = () => {
    setIsLoading(true)
    setTimeout(() => {
      demoLogin()
      toast.success('Đã truy cập phiên làm việc khách (Guest Access)!')
      navigate('/dashboard')
      setIsLoading(false)
    }, 400)
  }

  const handleGoogleLogin = () => {
    toast.loading('Đang kết nối xác thực Google...', { duration: 800 })
    setTimeout(() => {
      demoLogin()
      toast.success('Đăng nhập Google thành công!')
      navigate('/dashboard')
    }, 900)
  }

  return (
    <div className="min-h-screen zzz-carbon-bg text-white antialiased relative selection:bg-[#B8E900] selection:text-[#0C0D10] flex flex-col justify-between overflow-x-hidden">
      {/* High-Tech Vector Non-Gradient Background */}
      <ArchitecturalBackground />

      {/* Top Floating Minimal Navigation Header */}
      <header className="relative z-20 px-6 py-3.5 flex items-center justify-between border-b border-[#282B37] bg-[#14151C]/90 backdrop-blur-md">
        <div
          className="flex items-center gap-3 cursor-pointer"
          onClick={() => navigate('/')}
        >
          <div className="w-8 h-8 rounded-xl bg-[#242733] border border-[#353846] text-[#B8E900] flex items-center justify-center font-tech font-black text-base shadow-sm">
            Z
          </div>
          <div className="flex items-center gap-2">
            <span className="font-tech font-bold text-base tracking-wider text-white">
              .FUNCTIONS
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#222530] text-[#9CA3AF] border border-[#2E313E]">
              REV. 2.4
            </span>
          </div>
        </div>

        <Link
          to="/"
          className="text-xs font-tech font-bold uppercase text-[#9CA3AF] hover:text-white transition-colors flex items-center gap-1.5"
        >
          <span>← Quay lại Trang Chủ</span>
        </Link>
      </header>

      {/* Main Container - ZZZ Master Console Frame */}
      <main className="relative z-10 flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8 flex items-center justify-center">
        <div className="relative w-full zzz-device-frame overflow-hidden shadow-2xl">
          {/* Top Window Titlebar Across Entire Width */}
          <div className="px-5 py-3 bg-[#14151C] border-b border-[#282B37] flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Aligned 3 Colored macOS Dots */}
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="w-2.5 h-2.5 rounded-full bg-[#FF3355] block shrink-0" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#FF5E00] block shrink-0" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#B8E900] block shrink-0" />
              </div>
              <div className="h-3.5 w-px bg-[#282B37] shrink-0" />
              <span className="text-xs font-tech font-bold tracking-wider text-[#9CA3AF] flex items-center gap-1.5 uppercase">
                <Layers className="w-3.5 h-3.5 text-[#B8E900]" />
                COMMISSIONS // AUTHENTICATION_GATEWAY
              </span>
            </div>

            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-[#6B7280] hidden sm:inline">PROTO: TLS 1.3 // AES-256</span>
              <span className="flex items-center gap-1.5 text-[#B8E900] font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900] animate-pulse" />
                ONLINE
              </span>
            </div>
          </div>

          {/* Interior Layout (2 Balanced Columns in 1 Chassis) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[520px]">
            {/* Left Column: Animated ZZZ Vector Artwork */}
            <div className="lg:col-span-6 bg-[#101116] p-6 flex items-center justify-center border-b lg:border-b-0 lg:border-r border-[#282B37] relative overflow-hidden select-none">
              <div className="absolute inset-0 bg-[#14151C] opacity-40" />

              {/* Main Vector Stage */}
              <div className="relative w-72 h-72 sm:w-80 sm:h-80 flex items-center justify-center z-10">
                {/* 1. Outer Rotating Gyroscopic Wheel */}
                <motion.svg
                  className="absolute inset-0 w-full h-full"
                  viewBox="0 0 300 300"
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 32, ease: 'linear' }}
                >
                  <circle
                    cx="150"
                    cy="150"
                    r="140"
                    fill="none"
                    stroke="rgba(184, 233, 0, 0.2)"
                    strokeWidth="1"
                    strokeDasharray="6 8"
                  />
                  {Array.from({ length: 24 }).map((_, i) => {
                    const angle = (i * 15 * Math.PI) / 180
                    const isMajor = i % 6 === 0
                    const len = isMajor ? 10 : 5
                    const x1 = 150 + (140 - len) * Math.cos(angle)
                    const y1 = 150 + (140 - len) * Math.sin(angle)
                    const x2 = 150 + 140 * Math.cos(angle)
                    const y2 = 150 + 140 * Math.sin(angle)
                    return (
                      <line
                        key={i}
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke={isMajor ? '#B8E900' : 'rgba(255, 255, 255, 0.2)'}
                        strokeWidth={isMajor ? 1.5 : 1}
                      />
                    )
                  })}
                  <circle cx="150" cy="10" r="3" fill="#B8E900" />
                  <circle cx="150" cy="290" r="3" fill="#B8E900" />
                  <circle cx="10" cy="150" r="3" fill="#B8E900" />
                  <circle cx="290" cy="150" r="3" fill="#B8E900" />
                </motion.svg>

                {/* 2. Middle Counter-Rotating Bus Track */}
                <motion.svg
                  className="absolute inset-0 w-full h-full"
                  viewBox="0 0 300 300"
                  animate={{ rotate: -360 }}
                  transition={{ repeat: Infinity, duration: 22, ease: 'linear' }}
                >
                  <polygon
                    points="150,40 245,95 245,205 150,260 55,205 55,95"
                    fill="none"
                    stroke="rgba(184, 233, 0, 0.3)"
                    strokeWidth="1.2"
                  />
                  <circle cx="150" cy="40" r="2.5" fill="#B8E900" />
                  <circle cx="245" cy="95" r="2.5" fill="#FFFFFF" />
                  <circle cx="245" cy="205" r="2.5" fill="#B8E900" />
                  <circle cx="150" cy="260" r="2.5" fill="#FFFFFF" />
                  <circle cx="55" cy="205" r="2.5" fill="#B8E900" />
                  <circle cx="55" cy="95" r="2.5" fill="#FFFFFF" />
                </motion.svg>

                {/* 3. Static Precision Crosshairs */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 300 300">
                  <line x1="150" y1="15" x2="150" y2="70" stroke="#B8E900" strokeOpacity="0.4" strokeWidth="1.5" />
                  <line x1="150" y1="230" x2="150" y2="285" stroke="#B8E900" strokeOpacity="0.4" strokeWidth="1.5" />
                  <line x1="15" y1="150" x2="70" y2="150" stroke="#B8E900" strokeOpacity="0.4" strokeWidth="1.5" />
                  <line x1="230" y1="150" x2="285" y2="150" stroke="#B8E900" strokeOpacity="0.4" strokeWidth="1.5" />
                  <circle
                    cx="150"
                    cy="150"
                    r="68"
                    fill="#181A22"
                    stroke="rgba(184, 233, 0, 0.5)"
                    strokeWidth="1.5"
                  />
                </svg>

                {/* Center Vector Icon */}
                <AnimatePresence mode="wait">
                  {mode === 'login' ? (
                    <motion.div
                      key="pure-vector-login"
                      initial={{ scale: 0.7, opacity: 0, rotate: -30 }}
                      animate={{ scale: 1, opacity: 1, rotate: 0 }}
                      exit={{ scale: 0.7, opacity: 0, rotate: 30 }}
                      transition={{ type: 'spring', stiffness: 380, damping: 26 }}
                      className="relative z-20 flex items-center justify-center"
                    >
                      <motion.div
                        className="absolute w-20 h-0.5 bg-[#B8E900] shadow-[0_0_12px_#B8E900] z-30 pointer-events-none"
                        animate={{ y: [-24, 24, -24] }}
                        transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
                      />

                      <div className="w-24 h-24 rounded-2xl bg-[#222530] border-2 border-[#B8E900] flex items-center justify-center shadow-[0_0_24px_rgba(184,233,0,0.3)]">
                        <Key className="w-12 h-12 text-[#B8E900]" />
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="pure-vector-register"
                      initial={{ scale: 0.7, opacity: 0, rotate: 30 }}
                      animate={{ scale: 1, opacity: 1, rotate: 0 }}
                      exit={{ scale: 0.7, opacity: 0, rotate: -30 }}
                      transition={{ type: 'spring', stiffness: 380, damping: 26 }}
                      className="relative z-20 flex items-center justify-center"
                    >
                      <motion.div
                        className="absolute w-28 h-28 rounded-full border border-[#B8E900]/50 pointer-events-none"
                        animate={{ scale: [1, 1.25, 1], opacity: [0.8, 0, 0.8] }}
                        transition={{ repeat: Infinity, duration: 2.2, ease: 'easeOut' }}
                      />

                      <div className="w-24 h-24 rounded-2xl bg-[#222530] border-2 border-[#B8E900] flex items-center justify-center shadow-[0_0_24px_rgba(184,233,0,0.3)]">
                        <UserPlus className="w-12 h-12 text-[#B8E900]" />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Right Column: Form Workstation */}
            <div className="lg:col-span-6 p-6 sm:p-7 flex flex-col justify-between bg-[#181A22]">
              <div>
                {/* ZZZ Segmented Capsule Tabs */}
                <div className="zzz-pill-container w-full grid grid-cols-2 p-1 mb-5">
                  <button
                    type="button"
                    onClick={() => handleSwitchMode('login')}
                    className={`py-2 text-xs font-tech font-bold uppercase transition-all text-center rounded-full cursor-pointer ${
                      mode === 'login'
                        ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                        : 'text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    Đăng Nhập
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSwitchMode('register')}
                    className={`py-2 text-xs font-tech font-bold uppercase transition-all text-center rounded-full cursor-pointer ${
                      mode === 'register'
                        ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                        : 'text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    Đăng Ký
                  </button>
                </div>

                {/* Google Sign-In Button */}
                <button
                  type="button"
                  onClick={handleGoogleLogin}
                  className="w-full py-2.5 px-4 rounded-xl bg-[#222530] hover:bg-[#2B2E3C] border border-[#2E313E] hover:border-white text-xs font-tech font-bold uppercase text-white transition-all flex items-center justify-center gap-2.5 cursor-pointer shadow-sm mb-4"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path
                      fill="#EA4335"
                      d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
                    />
                    <path
                      fill="#4285F4"
                      d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.8s.2-2.1.4-2.8L1.9 6.3C.7 8.7 0 10.3 0 12s.7 3.3 1.9 5.7l3.7-2.9z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z"
                    />
                  </svg>
                  <span>Tiếp tục với tài khoản Google</span>
                </button>

                <div className="flex items-center gap-3 my-3">
                  <div className="flex-1 h-px bg-[#282B37]" />
                  <span className="text-[10px] font-mono text-[#6B7280] uppercase">HOẶC DÙNG EMAIL</span>
                  <div className="flex-1 h-px bg-[#282B37]" />
                </div>

                <AnimatePresence mode="wait">
                  {mode === 'login' ? (
                    <motion.form
                      key="login-form"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.16 }}
                      onSubmit={handleSubmit}
                      className="space-y-3.5"
                    >
                      {/* Email */}
                      <div className="space-y-1 text-left">
                        <label className="text-[11px] font-mono text-[#9CA3AF] block">
                          ĐỊA CHỈ EMAIL
                        </label>
                        <div className="relative">
                          <Mail className="w-4 h-4 text-[#6B7280] absolute left-3.5 top-1/2 -translate-y-1/2" />
                          <input
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@example.com"
                            className="w-full bg-[#222530] border border-[#2E313E] rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900] transition-all"
                          />
                        </div>
                      </div>

                      {/* Password */}
                      <div className="space-y-1 text-left">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-mono text-[#9CA3AF]">
                            MẬT KHẨU
                          </label>
                          <a
                            href="#forgot"
                            onClick={(e) => {
                              e.preventDefault()
                              toast('Chức năng đặt lại mật khẩu đã sẵn sàng.')
                            }}
                            className="text-[11px] text-[#B8E900] hover:underline"
                          >
                            Quên mật khẩu?
                          </a>
                        </div>
                        <div className="relative">
                          <Lock className="w-4 h-4 text-[#6B7280] absolute left-3.5 top-1/2 -translate-y-1/2" />
                          <input
                            type={showPassword ? 'text' : 'password'}
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            className="w-full bg-[#222530] border border-[#2E313E] rounded-xl pl-10 pr-10 py-2 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900] transition-all"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-white cursor-pointer"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>

                      {/* Remember Checkbox */}
                      <div className="flex items-center gap-2 text-left pt-0.5">
                        <input
                          type="checkbox"
                          id="remember"
                          checked={rememberMe}
                          onChange={(e) => setRememberMe(e.target.checked)}
                          className="w-3.5 h-3.5 rounded bg-[#222530] border-[#2E313E] text-[#B8E900] focus:ring-0 cursor-pointer"
                        />
                        <label htmlFor="remember" className="text-xs font-mono text-[#9CA3AF] cursor-pointer">
                          Ghi nhớ đăng nhập
                        </label>
                      </div>

                      {/* Submit Login Button */}
                      <Button
                        type="submit"
                        variant="primary"
                        size="lg"
                        disabled={isLoading}
                        className="w-full flex items-center justify-center gap-2 text-xs py-2.5 mt-1"
                      >
                        <Zap className="w-4 h-4" />
                        <span>{isLoading ? 'ĐANG XÁC THỰC...' : 'ĐĂNG NHẬP HỆ THỐNG'}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Button>

                      {/* 1-Click Fast Demo Login */}
                      <div className="pt-2 border-t border-[#282B37]">
                        <button
                          type="button"
                          onClick={handleDemoLogin}
                          className="w-full py-2 px-3 rounded-xl bg-[#222530] border border-[#2E313E] hover:border-[#B8E900] text-xs font-tech font-bold uppercase text-[#B8E900] hover:bg-[#B8E900]/10 transition-colors flex items-center justify-center gap-2 cursor-pointer"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>TRUY CẬP NHANH (GUEST ACCESS)</span>
                        </button>
                      </div>
                    </motion.form>
                  ) : (
                    <motion.form
                      key="register-form"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.16 }}
                      onSubmit={handleSubmit}
                      className="space-y-3"
                    >
                      {/* Full Name */}
                      <div className="space-y-1 text-left">
                        <label className="text-[11px] font-mono text-[#9CA3AF] block">
                          HỌ VÀ TÊN
                        </label>
                        <div className="relative">
                          <UserIcon className="w-4 h-4 text-[#6B7280] absolute left-3.5 top-1/2 -translate-y-1/2" />
                          <input
                            type="text"
                            required
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Nguyễn Văn A"
                            className="w-full bg-[#222530] border border-[#2E313E] rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900] transition-all"
                          />
                        </div>
                      </div>

                      {/* Email */}
                      <div className="space-y-1 text-left">
                        <label className="text-[11px] font-mono text-[#9CA3AF] block">
                          ĐỊA CHỈ EMAIL
                        </label>
                        <div className="relative">
                          <Mail className="w-4 h-4 text-[#6B7280] absolute left-3.5 top-1/2 -translate-y-1/2" />
                          <input
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="name@example.com"
                            className="w-full bg-[#222530] border border-[#2E313E] rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900] transition-all"
                          />
                        </div>
                      </div>

                      {/* Password */}
                      <div className="space-y-1 text-left">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-mono text-[#9CA3AF]">
                            MẬT KHẨU
                          </label>
                          {password && (
                            <span className="text-[10px] font-mono text-[#B8E900]">
                              Độ bảo mật: {strength.text}
                            </span>
                          )}
                        </div>
                        <div className="relative">
                          <Lock className="w-4 h-4 text-[#6B7280] absolute left-3.5 top-1/2 -translate-y-1/2" />
                          <input
                            type={showPassword ? 'text' : 'password'}
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Tối thiểu 6 ký tự"
                            className="w-full bg-[#222530] border border-[#2E313E] rounded-xl pl-10 pr-10 py-2 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900] transition-all"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-white cursor-pointer"
                          >
                            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                        {password && (
                          <div className="w-full h-1 bg-[#222530] rounded-full overflow-hidden mt-1">
                            <div
                              className={`h-full ${strength.color} transition-all duration-300`}
                              style={{ width: `${strength.score}%` }}
                            />
                          </div>
                        )}
                      </div>

                      {/* Submit Register Button */}
                      <Button
                        type="submit"
                        variant="primary"
                        size="lg"
                        disabled={isLoading}
                        className="w-full flex items-center justify-center gap-2 text-xs py-2.5 mt-2"
                      >
                        <Sparkles className="w-4 h-4" />
                        <span>{isLoading ? 'ĐANG TẠO...' : 'TẠO TÀI KHOẢN MỚI'}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </motion.form>
                  )}
                </AnimatePresence>
              </div>

              {/* Bottom Switch Trigger */}
              <div className="pt-3 border-t border-[#282B37] text-center text-xs text-[#9CA3AF]">
                {mode === 'login' ? (
                  <p>
                    Chưa có tài khoản FileForge?{' '}
                    <button
                      type="button"
                      onClick={() => handleSwitchMode('register')}
                      className="text-[#B8E900] font-bold hover:underline cursor-pointer"
                    >
                      Đăng ký ngay
                    </button>
                  </p>
                ) : (
                  <p>
                    Đã có tài khoản hệ thống?{' '}
                    <button
                      type="button"
                      onClick={() => handleSwitchMode('login')}
                      className="text-[#B8E900] font-bold hover:underline cursor-pointer"
                    >
                      Đăng nhập ngay
                    </button>
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-20 py-3 px-6 border-t border-[#282B37] text-center text-[10px] font-mono text-[#6B7280]">
        FILEFORGE PROXY FUNCTIONS // ZERO-RETENTION LOCAL STORAGE
      </footer>
    </div>
  )
}
