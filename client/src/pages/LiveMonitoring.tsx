import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Video, Plus, Camera as CameraIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { cameraService } from '@/services/cameraService'
import { locationService } from '@/services/locationService'
import { CameraTile } from '@/components/live/CameraTile'
import {
  LiveControlToolbar,
  GridLayout,
} from '@/components/live/LiveControlToolbar'
import { LiveEventPanel } from '@/components/live/LiveEventPanel'
import { CameraSelectorModal } from '@/components/live/CameraSelectorModal'
import type { Camera } from '@/types/api'

const LAYOUT_SLOT_COUNTS: Record<GridLayout, number> = {
  '1x1': 1,
  '2x2': 4,
  '3x3': 9,
  '4x4': 16,
}

const LAYOUT_GRID_CLASSES: Record<GridLayout, string> = {
  '1x1': 'grid-cols-1 max-w-5xl mx-auto',
  '2x2': 'grid-cols-1 md:grid-cols-2',
  '3x3': 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
  '4x4': 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4',
}

export const LiveMonitoring: React.FC = () => {
  const gridContainerRef = useRef<HTMLDivElement>(null)

  // Layout & Slot State
  const [layout, setLayout] = useState<GridLayout>('2x2')
  const [selectedCameraIds, setSelectedCameraIds] = useState<(number | null)[]>([
    null,
    null,
    null,
    null,
  ])
  const [selectedCameraForFocus, setSelectedCameraForFocus] = useState<number | null>(null)

  // Filter States
  const [selectedLocation, setSelectedLocation] = useState<string>('all')
  const [selectedRole, setSelectedRole] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')

  // UI Panels State
  const [showEventPanel, setShowEventPanel] = useState<boolean>(true)
  const [isSelectorOpen, setIsSelectorOpen] = useState<boolean>(false)
  const [isGridFullscreen, setIsGridFullscreen] = useState<boolean>(false)

  // Query genuine registered cameras
  const {
    data: cameraData,
    isLoading: isCamerasLoading,
    refetch: refetchCameras,
    isFetching: isCamerasFetching,
  } = useQuery({
    queryKey: ['cameras', 'live-monitoring'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 100 }),
    refetchInterval: 30000,
  })

  // Query genuine locations
  const { data: locations = [] } = useQuery({
    queryKey: ['locations', 'list'],
    queryFn: () => locationService.getLocations({ is_active: true }),
    staleTime: 60000,
  })

  const cameras: Camera[] = useMemo(() => cameraData?.items || [], [cameraData])

  // Map location IDs to names
  const locationMap = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((loc) => map.set(loc.id, loc.name))
    return map
  }, [locations])

  // Map camera IDs to objects
  const cameraMap = useMemo(() => {
    const map = new Map<number, Camera>()
    cameras.forEach((cam) => map.set(cam.id, cam))
    return map
  }, [cameras])

  // Fullscreen change listener for grid wall
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsGridFullscreen(document.fullscreenElement === gridContainerRef.current)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  const toggleGridFullscreen = () => {
    if (!gridContainerRef.current) return
    if (!document.fullscreenElement) {
      gridContainerRef.current.requestFullscreen().catch((err) => {
        console.error('Grid fullscreen request failed:', err)
      })
    } else {
      document.exitFullscreen().catch((err) => {
        console.error('Exit grid fullscreen failed:', err)
      })
    }
  }

  // Auto-initialize grid slots once when cameras load
  const hasAutoPopulatedRef = useRef<boolean>(false)
  useEffect(() => {
    if (!hasAutoPopulatedRef.current && cameras.length > 0) {
      hasAutoPopulatedRef.current = true
      const maxSlots = LAYOUT_SLOT_COUNTS[layout]
      const initialIds: (number | null)[] = []
      for (let i = 0; i < maxSlots; i++) {
        initialIds.push(cameras[i] ? cameras[i].id : null)
      }
      setSelectedCameraIds(initialIds)
    }
  }, [cameras, layout])

  // Adjust slots when layout changes
  const handleLayoutChange = (newLayout: GridLayout) => {
    setLayout(newLayout)
    const newCount = LAYOUT_SLOT_COUNTS[newLayout]
    setSelectedCameraIds((prev) => {
      const next = [...prev]
      if (next.length < newCount) {
        // Expand slots
        while (next.length < newCount) {
          next.push(null)
        }
      } else if (next.length > newCount) {
        // Shrink slots
        return next.slice(0, newCount)
      }
      return next
    })
  }

  // Auto-fill available online cameras into slots
  const handleAutoFillOnline = () => {
    const maxSlots = LAYOUT_SLOT_COUNTS[layout]
    const onlineCameras = cameras.filter((c) => c.connection_status === 'online')
    const candidates = onlineCameras.length > 0 ? onlineCameras : cameras

    const newSlots: (number | null)[] = []
    for (let i = 0; i < maxSlots; i++) {
      newSlots.push(candidates[i] ? candidates[i].id : null)
    }
    setSelectedCameraIds(newSlots)
  }

  // Clear grid
  const handleClearGrid = () => {
    const maxSlots = LAYOUT_SLOT_COUNTS[layout]
    setSelectedCameraIds(new Array(maxSlots).fill(null))
    setSelectedCameraForFocus(null)
  }

  // Assign specific camera to a specific slot index
  const handleAssignToSlot = (slotIndex: number, cameraId: number | null) => {
    setSelectedCameraIds((prev) => {
      const updated = [...prev]
      updated[slotIndex] = cameraId
      return updated
    })
  }

  // Apply selection from modal
  const handleApplyModalSelection = (selectedIds: number[]) => {
    const maxSlots = LAYOUT_SLOT_COUNTS[layout]
    const newSlots: (number | null)[] = []
    for (let i = 0; i < maxSlots; i++) {
      newSlots.push(selectedIds[i] ?? null)
    }
    setSelectedCameraIds(newSlots)
  }

  const assignedCount = selectedCameraIds.filter((id) => id !== null).length
  const maxSlots = LAYOUT_SLOT_COUNTS[layout]

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#070a0f] text-slate-100 overflow-hidden">
      {/* Page Header */}
      <div className="flex h-14 items-center justify-between border-b border-[#1e2633] px-6 bg-[#0c1017] shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">
            <Video className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide text-slate-100">
              Live Monitoring & CCTV Wall
            </h1>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              Authenticated MJPEG streaming, camera health heartbeats & live AI detection telemetry
            </p>
          </div>
        </div>

        {/* Global Live Summary */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-[#131924] border border-[#232d3f] text-xs">
            <span className="flex items-center gap-1.5 font-medium text-slate-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              {cameras.filter((c) => c.connection_status === 'online').length} Online
            </span>
            <span className="text-slate-600">/</span>
            <span className="text-slate-400 font-medium">
              {cameras.length} Registered
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left / Center Grid Viewport */}
        <div className="flex flex-1 flex-col p-4 overflow-y-auto gap-4">
          {/* Top Control Toolbar */}
          <LiveControlToolbar
            layout={layout}
            onChangeLayout={handleLayoutChange}
            locations={locations}
            selectedLocation={selectedLocation}
            onChangeLocation={setSelectedLocation}
            selectedRole={selectedRole}
            onChangeRole={setSelectedRole}
            selectedStatus={selectedStatus}
            onChangeStatus={setSelectedStatus}
            onOpenSelector={() => setIsSelectorOpen(true)}
            onAutoFillOnline={handleAutoFillOnline}
            onClearGrid={handleClearGrid}
            onRefreshAll={() => refetchCameras()}
            isRefreshing={isCamerasFetching}
            isGridFullscreen={isGridFullscreen}
            onToggleGridFullscreen={toggleGridFullscreen}
            showEventPanel={showEventPanel}
            onToggleEventPanel={() => setShowEventPanel(!showEventPanel)}
            totalAssignedTiles={assignedCount}
            totalAvailableCameras={cameras.length}
          />

          {/* Zero Cameras Registered in DB Notice */}
          {!isCamerasLoading && cameras.length === 0 && (
            <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-[#1e2633] rounded-2xl bg-[#0c1017] my-auto">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 mb-3">
                <CameraIcon className="h-6 w-6" />
              </div>
              <h2 className="text-sm font-bold text-slate-100">No CCTV Cameras Registered</h2>
              <p className="text-xs text-slate-400 mt-1 max-w-md">
                To start live video monitoring and AI telemetry analysis, register your CCTV camera infrastructure in the Camera Management module.
              </p>
              <Link
                to="/cameras"
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors shadow-lg shadow-cyan-600/20"
              >
                <Plus className="h-4 w-4" />
                Register Cameras Now
              </Link>
            </div>
          )}

          {/* Camera Grid Wall Container */}
          {cameras.length > 0 && (
            <div
              ref={gridContainerRef}
              className={cn(
                'grid gap-3 flex-1 transition-all duration-200',
                LAYOUT_GRID_CLASSES[layout],
                isGridFullscreen && 'p-4 bg-black overflow-y-auto'
              )}
            >
              {selectedCameraIds.map((camId, slotIndex) => {
                const camera = camId ? cameraMap.get(camId) : null

                if (!camera) {
                  // Empty Grid Tile Slot
                  return (
                    <div
                      key={`empty-slot-${slotIndex}`}
                      onClick={() => setIsSelectorOpen(true)}
                      className="group relative flex aspect-video flex-col items-center justify-center rounded-xl border border-dashed border-[#232d3f] bg-[#0c1017]/60 hover:bg-[#111724]/80 hover:border-cyan-500/50 transition-all duration-200 cursor-pointer select-none text-center p-4"
                    >
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 group-hover:bg-cyan-500/20 text-slate-400 group-hover:text-cyan-400 transition-colors mb-2">
                        <Plus className="h-5 w-5" />
                      </div>
                      <span className="text-xs font-semibold text-slate-300 group-hover:text-slate-100">
                        Assign Camera (Slot {slotIndex + 1})
                      </span>
                      <span className="text-[11px] text-slate-500 mt-0.5">
                        Click to select from {cameras.length} registered cameras
                      </span>
                    </div>
                  )
                }

                // Assigned Camera Tile
                return (
                  <CameraTile
                    key={`cam-tile-${camera.id}-${slotIndex}`}
                    camera={camera}
                    locationName={locationMap.get(camera.location_id)}
                    isSelected={selectedCameraForFocus === camera.id}
                    onSelect={() => setSelectedCameraForFocus(camera.id)}
                    onRemove={() => handleAssignToSlot(slotIndex, null)}
                  />
                )
              })}
            </div>
          )}
        </div>

        {/* Live Event Activity Feed Panel */}
        <LiveEventPanel
          cameras={cameras}
          selectedCameraId={selectedCameraForFocus}
          onSelectCamera={(id) => setSelectedCameraForFocus(id)}
          isOpen={showEventPanel}
          onToggle={() => setShowEventPanel(!showEventPanel)}
        />
      </div>

      {/* Camera Selection Modal */}
      <CameraSelectorModal
        isOpen={isSelectorOpen}
        onClose={() => setIsSelectorOpen(false)}
        cameras={cameras}
        locations={locations}
        selectedCameraIds={selectedCameraIds}
        onApplySelection={handleApplyModalSelection}
        maxSlots={maxSlots}
      />
    </div>
  )
}

export default LiveMonitoring
