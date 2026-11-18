import React from 'react'
import {
  Maximize2,
  Minimize2,
  RefreshCw,
  SlidersHorizontal,
  Building2,
  Activity,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Location } from '@/types/api'

export type GridLayout = '1x1' | '2x2' | '3x3' | '4x4'

interface LiveControlToolbarProps {
  layout: GridLayout
  onChangeLayout: (layout: GridLayout) => void
  locations: Location[]
  selectedLocation: string
  onChangeLocation: (locationId: string) => void
  selectedRole: string
  onChangeRole: (role: string) => void
  selectedStatus: string
  onChangeStatus: (status: string) => void
  onOpenSelector: () => void
  onAutoFillOnline: () => void
  onClearGrid: () => void
  onRefreshAll: () => void
  isRefreshing: boolean
  isGridFullscreen: boolean
  onToggleGridFullscreen: () => void
  showEventPanel: boolean
  onToggleEventPanel: () => void
  totalAssignedTiles: number
  totalAvailableCameras: number
}

const LAYOUTS: { id: GridLayout; label: string; iconSize: string; count: number }[] = [
  { id: '1x1', label: '1×1', iconSize: 'h-4 w-4', count: 1 },
  { id: '2x2', label: '2×2', iconSize: 'h-4 w-4', count: 4 },
  { id: '3x3', label: '3×3', iconSize: 'h-4 w-4', count: 9 },
  { id: '4x4', label: '4×4', iconSize: 'h-4 w-4', count: 16 },
]

export const LiveControlToolbar: React.FC<LiveControlToolbarProps> = ({
  layout,
  onChangeLayout,
  locations,
  selectedLocation,
  onChangeLocation,
  selectedRole,
  onChangeRole,
  selectedStatus,
  onChangeStatus,
  onOpenSelector,
  onAutoFillOnline,
  onClearGrid,
  onRefreshAll,
  isRefreshing,
  isGridFullscreen,
  onToggleGridFullscreen,
  showEventPanel,
  onToggleEventPanel,
  totalAssignedTiles,
  totalAvailableCameras,
}) => {
  return (
    <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 bg-[#0c1017] border border-[#1e2633] rounded-xl shadow-lg">
      {/* Left: Layout Matrix & Camera Grid Selection */}
      <div className="flex items-center flex-wrap gap-2">
        {/* Layout Buttons Group */}
        <div className="flex items-center bg-[#131924] border border-[#232d3f] rounded-lg p-1">
          {LAYOUTS.map((item) => (
            <button
              key={item.id}
              onClick={() => onChangeLayout(item.id)}
              className={cn(
                'px-2.5 py-1 rounded text-xs font-semibold tracking-wider transition-all duration-150',
                layout === item.id
                  ? 'bg-cyan-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              )}
              title={`${item.label} Grid (${item.count} Camera Slots)`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Camera Selector Button */}
        <button
          onClick={onOpenSelector}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#131924] hover:bg-[#182030] text-slate-200 border border-[#232d3f] transition-colors"
        >
          <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-400" />
          <span>Assign Cameras</span>
          <span className="ml-1 rounded-full bg-cyan-500/20 px-1.5 py-0.2 text-[10px] font-mono text-cyan-300">
            {totalAssignedTiles} / {totalAvailableCameras}
          </span>
        </button>

        {/* Auto-Fill Online Button */}
        <button
          onClick={onAutoFillOnline}
          className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-[#131924] hover:bg-[#182030] border border-[#232d3f] transition-colors"
          title="Auto-populate grid with active online cameras"
        >
          <Sparkles className="h-3.5 w-3.5 text-amber-400" />
          <span>Auto-Fill</span>
        </button>

        {/* Clear Grid Button */}
        {totalAssignedTiles > 0 && (
          <button
            onClick={onClearGrid}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            title="Clear all camera tiles"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Middle/Right: Filters & Actions */}
      <div className="flex items-center flex-wrap gap-2 justify-end">
        {/* Location Filter */}
        <div className="flex items-center bg-[#131924] border border-[#232d3f] rounded-lg px-2">
          <Building2 className="h-3.5 w-3.5 text-slate-400 mr-1.5 shrink-0" />
          <select
            value={selectedLocation}
            onChange={(e) => onChangeLocation(e.target.value)}
            className="bg-transparent py-1.5 text-xs text-slate-200 focus:outline-none"
          >
            <option value="all">All Locations</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id.toString()}>
                {loc.name}
              </option>
            ))}
          </select>
        </div>

        {/* Role Filter */}
        <select
          value={selectedRole}
          onChange={(e) => onChangeRole(e.target.value)}
          className="bg-[#131924] border border-[#232d3f] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
        >
          <option value="all">All Roles</option>
          <option value="entry_exit">Entry / Exit</option>
          <option value="workstation">Workstation</option>
          <option value="perimeter">Perimeter</option>
          <option value="general">General</option>
        </select>

        {/* Status Filter */}
        <select
          value={selectedStatus}
          onChange={(e) => onChangeStatus(e.target.value)}
          className="bg-[#131924] border border-[#232d3f] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="online">Online Only</option>
          <option value="offline">Offline Only</option>
        </select>

        {/* Refresh All */}
        <button
          onClick={onRefreshAll}
          disabled={isRefreshing}
          className="p-1.5 rounded-lg bg-[#131924] hover:bg-[#182030] border border-[#232d3f] text-slate-300 hover:text-white transition-colors"
          title="Refresh camera data & reconnect feeds"
        >
          <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
        </button>

        {/* Grid Fullscreen Toggle */}
        <button
          onClick={onToggleGridFullscreen}
          className="p-1.5 rounded-lg bg-[#131924] hover:bg-[#182030] border border-[#232d3f] text-slate-300 hover:text-white transition-colors"
          title={isGridFullscreen ? 'Exit Fullscreen Wall' : 'Fullscreen Video Wall'}
        >
          {isGridFullscreen ? (
            <Minimize2 className="h-4 w-4" />
          ) : (
            <Maximize2 className="h-4 w-4" />
          )}
        </button>

        {/* Toggle Live Event Panel */}
        <button
          onClick={onToggleEventPanel}
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-150',
            showEventPanel
              ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              : 'bg-[#131924] text-slate-400 border-[#232d3f] hover:text-slate-200'
          )}
          title="Toggle Live Event Activity Stream"
        >
          <Activity className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Events</span>
        </button>
      </div>
    </div>
  )
}
