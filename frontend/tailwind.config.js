/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Exact Zenless Zone Zero (ZZZ) In-Game Colors extracted from Screenshots:
        // Dominant: Carbon Black, Deep Graphite Panels, Dark Slate Tiles, Stark White Text
        // Accent: ZZZ Signature Lime-Chartreuse (#B8E900 / #C6F202) used sparingly for active states
        zzz: {
          bg: '#101116',
          panel: '#181A22',
          surface: '#222530',
          tile: '#282B37',
          'tile-hover': '#323646',
          border: '#323646',
          'border-light': '#454A5E',
          text: '#FFFFFF',
          'text-muted': '#9CA3AF',
          'text-dim': '#6B7280',
          // Signature ZZZ In-Game Accent: Lime-Chartreuse
          lime: '#B8E900',
          'lime-bright': '#C6F202',
          'lime-glow': 'rgba(184, 233, 0, 0.4)',
          // Secondary alert states
          orange: '#FF5E00',
          red: '#FF3355',
        },
        bg: {
          void: '#0C0D12',
          primary: '#101116',
          secondary: '#181A22',
          tertiary: '#222530',
          elevated: '#282B37',
        },
      },
      fontFamily: {
        pixel: ['VT323', 'monospace'],
        tech: ['Chakra Petch', 'system-ui', 'sans-serif'],
        display: ['Chakra Petch', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Space Mono', 'monospace'],
        sans: ['Plus Jakarta Sans', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        'zzz-pill': '0 2px 8px rgba(0, 0, 0, 0.6)',
        'zzz-tile': '0 4px 12px rgba(0, 0, 0, 0.5)',
        'zzz-lime': '0 0 15px rgba(184, 233, 0, 0.35)',
        'zzz-card': '0 8px 24px rgba(0, 0, 0, 0.7)',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
