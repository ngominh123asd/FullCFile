import { useState } from 'react'
import { Terminal, Copy, Check } from 'lucide-react'
import { copyText } from '../../lib/utils'
import toast from 'react-hot-toast'
import { API_PUBLIC_URL } from '../../lib/api'

const SNIPPETS = {
  curl: `curl -X POST "${API_PUBLIC_URL}/convert" \\
  -H "Content-Type: application/json" \\
  -d '{
    "input_file_id": "file_uuid_here",
    "output_format": "docx",
    "options": {
      "template": "academic",
      "toc": true
    }
  }'`,
  python: `import requests

url = "${API_PUBLIC_URL}/ocr/process"
payload = {
    "input_file_id": "file_uuid_here",
    "output_format": "docx",
    "language": "vi",
    "preserve_tables": True
}

response = requests.post(url, json=payload)
job = response.json()
print("Job ID:", job["id"])`,
  javascript: `const response = await fetch("${API_PUBLIC_URL}/spreadsheet/convert", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    input_file_id: "file_uuid_here",
    output_format: "json",
    options: { include_header: true }
  })
});
const result = await response.json();
console.log("Converted result:", result);`,
  go: `package main

import (
    "bytes"
    "fmt"
    "net/http"
)

func main() {
    jsonData := []byte(\`{"input_file_id": "file_uuid_here", "output_format": "pdf"}\`)
    resp, err := http.Post("${API_PUBLIC_URL}/convert", "application/json", bytes.NewBuffer(jsonData))
    if err != nil {
        panic(err)
    }
    defer resp.Body.Close()
    fmt.Println("Status:", resp.Status)
}`,
}

export default function ApiPlayground() {
  const [activeLang, setActiveLang] = useState<'curl' | 'python' | 'javascript' | 'go'>('curl')
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const ok = await copyText(SNIPPETS[activeLang])
    if (ok) {
      setCopied(true)
      toast.success('Đã sao chép mã API!')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="w-full rounded-2xl bg-[#181A22] border-2 border-[#2C2F3D] overflow-hidden shadow-2xl">
      {/* Top Header */}
      <div className="p-4 bg-[#14151C] border-b border-[#282B37] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#242733] border border-[#353846] flex items-center justify-center text-[#B8E900]">
            <Terminal className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-tech font-bold text-white uppercase tracking-wider">
            REST API // PROXY INTEGRATION
          </span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#222530] text-[#B8E900] border border-[#2E313E]">
            v1.0 • PUBLIC
          </span>
        </div>

        {/* Language Tabs - ZZZ Pill style */}
        <div className="flex items-center gap-1 bg-[#181A22] p-1 rounded-full border border-[#282B37]">
          {(['curl', 'python', 'javascript', 'go'] as const).map((lang) => (
            <button
              key={lang}
              onClick={() => setActiveLang(lang)}
              className={`px-3 py-1 rounded-full text-xs font-tech font-bold uppercase transition-all ${
                activeLang === lang
                  ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                  : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
              }`}
            >
              {lang}
            </button>
          ))}
        </div>
      </div>

      {/* Code Display */}
      <div className="relative p-5 bg-[#101116]">
        <button
          onClick={handleCopy}
          className="absolute top-4 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-tech font-bold uppercase bg-[#222530] border border-[#2E313E] text-[#9CA3AF] hover:text-white hover:border-[#B8E900] transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-[#B8E900]" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'ĐÃ CHÉP' : 'SAO CHÉP'}</span>
        </button>

        <pre className="font-mono text-xs text-[#E6EDF3] leading-relaxed overflow-x-auto pr-28 max-h-[320px] custom-scrollbar">
          <code>{SNIPPETS[activeLang]}</code>
        </pre>
      </div>

      {/* Endpoints Quick Reference */}
      <div className="p-3.5 sm:p-4 bg-[#14151C] border-t border-[#282B37] grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs font-mono">
        <div className="p-2.5 rounded-xl bg-[#222530] border border-[#2E313E] flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full bg-[#181A22] text-[#B8E900] font-bold text-[10px] border border-[#282B37]">POST</span>
          <span className="text-white truncate">/api/v1/convert</span>
        </div>
        <div className="p-2.5 rounded-xl bg-[#222530] border border-[#2E313E] flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full bg-[#181A22] text-[#B8E900] font-bold text-[10px] border border-[#282B37]">POST</span>
          <span className="text-white truncate">/api/v1/ocr/process</span>
        </div>
        <div className="p-2.5 rounded-xl bg-[#222530] border border-[#2E313E] flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full bg-[#181A22] text-[#B8E900] font-bold text-[10px] border border-[#282B37]">POST</span>
          <span className="text-white truncate">/api/v1/spreadsheet/convert</span>
        </div>
      </div>
    </div>
  )
}
