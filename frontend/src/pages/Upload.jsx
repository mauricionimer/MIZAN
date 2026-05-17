import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, FileText, AlertCircle, Loader2 } from 'lucide-react'
import { useAnalysis } from '../context/AnalysisContext'
import { analisarCarteira } from '../api'

export default function Upload() {
  const [file, setFile] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef()
  const navigate = useNavigate()
  const { setResult } = useAnalysis()

  const handleFile = (f) => {
    if (!f) return
    if (!f.name.endsWith('.csv')) { setError('Apenas arquivos .csv são aceitos.'); return }
    setError(null)
    setFile(f)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [])

  const onDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const onDragLeave = (e) => { e.preventDefault(); setIsDragging(false) }

  const analisar = async () => {
    if (!file || loading) return
    setLoading(true)
    setError(null)
    try {
      const data = await analisarCarteira(file)
      setResult(data)
      navigate('/dashboard')
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  const fmtSize = (bytes) => bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      {/* Logo */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white text-lg font-bold">⚖</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Mizan</h1>
        </div>
        <p className="text-slate-500 text-sm">Plataforma de análise de carteira de crédito com IA</p>
      </div>

      {/* Card */}
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <h2 className="text-base font-semibold text-slate-800 mb-1">Carregar carteira</h2>
        <p className="text-sm text-slate-500 mb-6">
          Selecione o arquivo CSV com os dados dos devedores para iniciar a análise com IA.
        </p>

        {/* Drop zone */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current.click()}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          className={`
            border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
            transition-all duration-200 select-none
            ${isDragging
              ? 'border-blue-400 bg-blue-50 scale-[1.01]'
              : file
                ? 'border-emerald-300 bg-emerald-50'
                : 'border-slate-300 hover:border-blue-300 hover:bg-slate-50'}
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => handleFile(e.target.files[0])}
          />

          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileText className="h-10 w-10 text-emerald-500" />
              <p className="font-semibold text-slate-800">{file.name}</p>
              <p className="text-sm text-slate-400">{fmtSize(file.size)}</p>
              <p className="text-xs text-blue-500 mt-1">Clique para trocar o arquivo</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <UploadCloud className={`h-10 w-10 transition-colors ${isDragging ? 'text-blue-400' : 'text-slate-300'}`} />
              <div>
                <p className="font-medium text-slate-600">Arraste o CSV aqui</p>
                <p className="text-sm text-slate-400 mt-0.5">ou clique para selecionar</p>
              </div>
              <p className="text-xs text-slate-300 mt-1">Apenas arquivos .csv</p>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Button */}
        <button
          onClick={analisar}
          disabled={!file || loading}
          className={`
            mt-5 w-full py-3 rounded-xl font-semibold text-sm text-white
            flex items-center justify-center gap-2 transition-all duration-200
            ${!file || loading
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 shadow-sm active:scale-[0.98]'}
          `}
        >
          {loading
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Analisando carteira...</>
            : 'Analisar carteira'}
        </button>

        {/* Hint */}
        <p className="mt-4 text-center text-xs text-slate-400">
          Colunas esperadas: cpf, nome, produto, status, uf, valor_divida, renda_estimada, dias_em_atraso
        </p>
      </div>
    </div>
  )
}
