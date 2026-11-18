import React from 'react'
import { LucideIcon, HardDrive, Shield } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  subtitle: string
  badge?: string
  icon: LucideIcon
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  subtitle,
  badge = 'PHASE 2',
  icon: Icon,
}) => {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 border-b border-[#1e2633] pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              {title}
              <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                {badge}
              </span>
            </h1>
            <p className="text-xs font-mono text-slate-400">{subtitle}</p>
          </div>
        </div>
      </div>

      <div className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-[#1e2633] bg-[#0d1117] p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[#232c3d] bg-[#12161f] text-slate-400 mb-4">
          <Icon className="h-7 w-7 text-slate-400" />
        </div>
        <h3 className="text-base font-semibold text-slate-200 font-mono uppercase tracking-wider">
          {title} Module Ready
        </h3>
        <p className="mt-1 max-w-md text-xs text-slate-400">
          This command center module has been registered with routing and RBAC permissions. Full data visualization and interactive controls will be mounted in upcoming sprints.
        </p>
        <div className="mt-6 flex items-center gap-4 text-xs font-mono text-slate-400">
          <span className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald-400" />
            RBAC PROTECTED
          </span>
          <span className="flex items-center gap-1.5">
            <HardDrive className="h-3.5 w-3.5 text-blue-400" />
            BACKEND CONNECTED
          </span>
        </div>
      </div>
    </div>
  )
}

export default PlaceholderPage
