import React, { useState } from 'react'
import {
  Shield,
  Star,
  CheckCircle2,
  Trash2,
  AlertCircle,
  Clock,
  Sparkles,
} from 'lucide-react'

import { faceEnrollmentService } from '@/services/faceEnrollmentService'
import type { FaceEnrollment } from '@/types/api'

interface FaceTemplateListProps {
  employeeId: number
  templates: FaceEnrollment[]
  isLoading: boolean
  canManage: boolean
  onRefresh: () => void
}

export const FaceTemplateList: React.FC<FaceTemplateListProps> = ({
  templates,
  isLoading,
  canManage,
  onRefresh,
}) => {
  const [actionError, setActionError] = useState<string | null>(null)
  const [processingId, setProcessingId] = useState<number | null>(null)

  const handleSetPrimary = async (embeddingId: number) => {
    setActionError(null)
    setProcessingId(embeddingId)
    try {
      await faceEnrollmentService.setPrimaryTemplate(embeddingId)
      onRefresh()
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to designate primary template.')
    } finally {
      setProcessingId(null)
    }
  }

  const handleDeactivate = async (embeddingId: number) => {
    setActionError(null)
    setProcessingId(embeddingId)
    try {
      await faceEnrollmentService.deactivateEnrollment(embeddingId)
      onRefresh()
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to deactivate face template.')
    } finally {
      setProcessingId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-xs font-mono text-slate-400">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mr-2" />
        Loading biometric template records...
      </div>
    )
  }

  return (
    <div className="space-y-3 font-mono">
      {actionError && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <div>{actionError}</div>
        </div>
      )}

      {templates.length === 0 ? (
        <div className="rounded-lg border border-[#1b2331] bg-[#090d14] p-6 text-center">
          <Shield className="h-8 w-8 text-slate-600 mx-auto mb-2" />
          <h4 className="text-xs font-semibold text-slate-300 uppercase">
            No Biometric Templates Found
          </h4>
          <p className="text-[11px] text-slate-500 mt-1 max-w-sm mx-auto">
            This employee has not been enrolled with AuraFace recognition templates.
            Enroll a reference portrait to enable facial recognition across camera streams.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {templates.map((tmpl) => {
            const isProcessing = processingId === tmpl.id
            const qualityPct =
              tmpl.quality_score !== null && tmpl.quality_score !== undefined
                ? `${Math.round(tmpl.quality_score * 100)}%`
                : 'N/A'

            return (
              <div
                key={tmpl.id}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border p-3.5 transition-colors ${
                  tmpl.is_template && tmpl.is_active
                    ? 'border-emerald-500/40 bg-emerald-500/5'
                    : tmpl.is_active
                    ? 'border-[#1f293d] bg-[#0d131f]'
                    : 'border-[#18202e] bg-[#090d14]/70 opacity-60'
                }`}
              >
                {/* Left: Template info */}
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
                      tmpl.is_template && tmpl.is_active
                        ? 'border border-emerald-500/30 bg-emerald-500/20 text-emerald-400'
                        : 'border border-slate-700 bg-slate-800 text-slate-400'
                    }`}
                  >
                    {tmpl.is_template ? (
                      <Star className="h-3.5 w-3.5 fill-current" />
                    ) : (
                      <Shield className="h-3.5 w-3.5" />
                    )}
                  </div>

                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold text-slate-200">
                        {tmpl.model_name}
                      </span>
                      <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">
                        {tmpl.model_version}
                      </span>

                      {tmpl.is_template && tmpl.is_active && (
                        <span className="flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" />
                          PRIMARY ACTIVE
                        </span>
                      )}

                      {!tmpl.is_active && (
                        <span className="rounded border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-[10px] text-slate-400">
                          DEACTIVATED
                        </span>
                      )}
                    </div>

                    {/* Metadata tags */}
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400 mt-1.5">
                      <span className="flex items-center gap-1">
                        <Sparkles className="h-3 w-3 text-emerald-400" />
                        Quality: <strong className="text-slate-200">{qualityPct}</strong>
                      </span>
                      <span>
                        Samples: <strong className="text-slate-200">{tmpl.sample_count}</strong>
                      </span>
                      <span>
                        Dimension: <strong className="text-slate-200">{tmpl.embedding_dim || 512}D</strong>
                      </span>
                      {tmpl.source_image_ref && (
                        <span className="truncate max-w-[150px] text-slate-400" title={tmpl.source_image_ref}>
                          Ref: {tmpl.source_image_ref}
                        </span>
                      )}
                      <span className="flex items-center gap-1 text-[10px] text-slate-500">
                        <Clock className="h-3 w-3" />
                        {new Date(tmpl.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                {canManage && tmpl.is_active && (
                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                    {!tmpl.is_template && (
                      <button
                        type="button"
                        onClick={() => handleSetPrimary(tmpl.id)}
                        disabled={isProcessing}
                        className="flex items-center gap-1.5 rounded border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                      >
                        <Star className="h-3 w-3" />
                        Set Primary
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeactivate(tmpl.id)}
                      disabled={isProcessing}
                      title="Deactivate face template"
                      className="rounded border border-rose-500/30 bg-rose-500/10 p-1.5 text-rose-400 hover:bg-rose-500/20 transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
