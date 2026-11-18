import React, { useState } from 'react'
import {
  X,
  Search,
  Check,
  Camera as CameraIcon,
  Wifi,
  WifiOff,
  Building2,
  CheckSquare,
  Square,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Camera, Location } from '@/types/api'

interface CameraSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  cameras: Camera[]
  locations: Location[]
  selectedCameraIds: (number | null)[]
  onApplySelection: (selectedIds: number[]) => void
  maxSlots: number
}

export const CameraSelectorModal: React.FC<CameraSelectorModalProps> = ({
  isOpen,
  onClose,
  cameras,
  locations,
  selectedCameraIds,
  onApplySelection,
  maxSlots,
}) => {
  const [search, setSearch] = useState('')
  const [selectedLocationId, setSelectedLocationId] = useState<string>('all')
  const [selectedRole, setSelectedRole] = useState<string>('all')
  const [tempSelected, setTempSelected] = useState<number[]>(() =>
    selectedCameraIds.filter((id): id is number => id !== null)
  )

  if (!isOpen) return null

  // Map location names
  const locationMap = new Map<number, string>()
  locations.forEach((loc) => locationMap.set(loc.id, loc.name))

  // Filter cameras
  const filteredCameras = cameras.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.camera_code.toLowerCase().includes(search.toLowerCase())
    const matchesLocation =
      selectedLocationId === 'all' || c.location_id.toString() === selectedLocationId
    const matchesRole = selectedRole === 'all' || c.camera_role === selectedRole
    return matchesSearch && matchesLocation && matchesRole
  })

  const toggleCamera = (id: number) => {
    if (tempSelected.includes(id)) {
      setTempSelected(tempSelected.filter((item) => item !== id))
    } else {
      if (tempSelected.length >= maxSlots) {
        // Replace oldest or alert max reached
        alert(`Grid layout currently supports at most ${maxSlots} camera tiles. Please deselect a camera first.`)
        return
      }
      setTempSelected([...tempSelected, id])
    }
  }

  const selectAllFiltered = () => {
    const idsToAdd = filteredCameras.map((c) => c.id).slice(0, maxSlots)
    setTempSelected(idsToAdd)
  }

  const clearSelection = () => {
    setTempSelected([])
  }

  const handleApply = () => {
    onApplySelection(tempSelected)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="flex flex-col w-full max-w-2xl max-h-[85vh] rounded-2xl border border-[#1e2633] bg-[#0c1017] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b border-[#1e2633] px-6 bg-[#0e1420]">
          <div className="flex items-center gap-2">
            <CameraIcon className="h-5 w-5 text-cyan-400" />
            <h3 className="text-sm font-bold text-slate-100">
              Select Cameras for Live Wall ({tempSelected.length}/{maxSlots})
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filter Toolbar */}
        <div className="p-4 border-b border-[#1e2633] bg-[#090d14] flex flex-wrap gap-2.5">
          {/* Search */}
          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search code or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-[#131924] border border-[#232d3f] rounded-lg text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Location */}
          <select
            value={selectedLocationId}
            onChange={(e) => setSelectedLocationId(e.target.value)}
            className="bg-[#131924] border border-[#232d3f] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Locations</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id.toString()}>
                {loc.name}
              </option>
            ))}
          </select>

          {/* Role */}
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="bg-[#131924] border border-[#232d3f] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Roles</option>
            <option value="entry_exit">Entry / Exit</option>
            <option value="workstation">Workstation</option>
            <option value="perimeter">Perimeter</option>
            <option value="general">General</option>
          </select>

          {/* Quick Selection Buttons */}
          <button
            onClick={selectAllFiltered}
            className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
          >
            Select Filtered
          </button>
          <button
            onClick={clearSelection}
            className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-400 bg-slate-800/60 hover:bg-rose-500/10 transition-colors"
          >
            Clear
          </button>
        </div>

        {/* Camera List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {filteredCameras.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500">
              <CameraIcon className="h-8 w-8 text-slate-600 mb-2" />
              <p className="text-xs font-semibold text-slate-400">No cameras found</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Adjust search query or filter criteria.
              </p>
            </div>
          ) : (
            filteredCameras.map((cam) => {
              const isChecked = tempSelected.includes(cam.id)
              const locName = locationMap.get(cam.location_id) || `Location #${cam.location_id}`
              const isOnline = cam.connection_status === 'online'

              return (
                <div
                  key={cam.id}
                  onClick={() => toggleCamera(cam.id)}
                  className={cn(
                    'flex items-center justify-between p-3 rounded-xl border transition-all duration-150 cursor-pointer select-none',
                    isChecked
                      ? 'border-cyan-500/70 bg-cyan-950/20'
                      : 'border-[#1e2633] bg-[#0f141f] hover:bg-[#141b29] hover:border-slate-700'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-cyan-400">
                      {isChecked ? (
                        <CheckSquare className="h-5 w-5 text-cyan-400" />
                      ) : (
                        <Square className="h-5 w-5 text-slate-600" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-100">
                          {cam.camera_code}
                        </span>
                        <span className="text-xs text-slate-300 font-medium">
                          {cam.name}
                        </span>
                        {!cam.is_active && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            Inactive
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2.5 text-[11px] text-slate-400 mt-0.5">
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3 w-3 text-slate-500" />
                          {locName}
                        </span>
                        <span>•</span>
                        <span className="uppercase text-[10px] text-slate-400">
                          {cam.camera_role.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Status Indicator */}
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase border',
                        isOnline
                          ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                          : 'text-slate-400 bg-slate-800 border-slate-700'
                      )}
                    >
                      {isOnline ? (
                        <Wifi className="h-3 w-3" />
                      ) : (
                        <WifiOff className="h-3 w-3" />
                      )}
                      {cam.connection_status}
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[#1e2633] px-6 py-3 bg-[#0e1420]">
          <span className="text-xs text-slate-400">
            {tempSelected.length} of {maxSlots} active slots selected
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors shadow-md shadow-cyan-600/20"
            >
              <Check className="h-4 w-4" />
              Apply Grid
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
