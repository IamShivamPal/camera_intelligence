import React, { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Maximize2,
  Minimize2,
  RefreshCw,
  Camera as CameraIcon,
  Layers,
  Activity,
  AlertTriangle,
  Wifi,
  WifiOff,
  Clock,
  X,
  Download,
  AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/useAuth'
import { useMjpegStream } from '@/hooks/useMjpegStream'
import { zoneService } from '@/services/zoneService'
import { eventService } from '@/services/eventService'
import { PolygonOverlay } from '@/components/live/PolygonOverlay'
import { DetectionOverlay } from '@/components/live/DetectionOverlay'
import type { Camera, DetectionEvent } from '@/types/api'

interface CameraTileProps {
  camera: Camera
  locationName?: string
  onRemove?: () => void
  onSelect?: () => void
  isSelected?: boolean
}

export const CameraTile: React.FC<CameraTileProps> = ({
  camera,
  locationName,
  onRemove,
  onSelect,
  isSelected = false,
}) => {
  const { token } = useAuth()
  const tileRef = useRef<HTMLDivElement>(null)

  // Local tile controls
  const [showPolygons, setShowPolygons] = useState<boolean>(true)
  const [showDetections, setShowDetections] = useState<boolean>(true)
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === tileRef.current)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  const toggleFullscreen = () => {
    if (!tileRef.current) return
    if (!document.fullscreenElement) {
      tileRef.current.requestFullscreen().catch((err) => {
        console.error('Fullscreen request failed:', err)
      })
    } else {
      document.exitFullscreen().catch((err) => {
        console.error('Exit fullscreen failed:', err)
      })
    }
  }

  // Stream Hook: Native fetch with Bearer token, no query token
  const {
    currentFrameUrl,
    isLoading: isStreamLoading,
    isStreaming,
    error: streamError,
    errorCode: streamErrorCode,
    fps,
    totalFrames,
    reconnect,
    takeSnapshot,
  } = useMjpegStream({
    cameraId: camera.id,
    token,
    enabled: camera.is_active,
    fps: 15,
    quality: 75,
  })

  // Reactive clock state for pure heartbeat formatting
  const [now, setNow] = useState<number>(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10000)
    return () => clearInterval(timer)
  }, [])

  // Fetch Workstation Zones for this specific camera
  const { data: zonesData } = useQuery({
    queryKey: ['zones', 'camera', camera.id],
    queryFn: () => zoneService.getZones({ camera_id: camera.id, is_active: true, size: 50 }),
    staleTime: 60000,
  })

  // Fetch recent detection events for this specific camera (bounded polling every 5s)
  const { data: eventsData } = useQuery({
    queryKey: ['events', 'camera', camera.id],
    queryFn: () => eventService.getEvents({ camera_id: camera.id, size: 10 }),
    refetchInterval: 5000,
    staleTime: 4000,
  })

  const cameraZones = zonesData?.items || []
  const recentEvents: DetectionEvent[] = eventsData?.items || []

  // Derive genuine occupancy states from recent events
  const occupancyStatus: Record<number, { state: 'active' | 'idle' | 'vacant'; employeeName?: string }> = {}
  recentEvents.forEach((ev) => {
    if (ev.workstation_zone_id) {
      if (ev.event_type === 'workstation_active') {
        occupancyStatus[ev.workstation_zone_id] = { state: 'active' }
      } else if (ev.event_type === 'workstation_idle') {
        occupancyStatus[ev.workstation_zone_id] = { state: 'idle' }
      }
    }
  })

  // Format connection status
  const statusColor =
    camera.connection_status === 'online'
      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
      : camera.connection_status === 'degraded'
      ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
      : camera.connection_status === 'offline'
      ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
      : 'text-slate-400 bg-slate-500/10 border-slate-500/30'

  // Format last heartbeat using reactive clock
  const formatHeartbeat = (ts?: string | null) => {
    if (!ts) return 'Never'
    const diff = Math.floor((now - new Date(ts).getTime()) / 1000)
    if (diff < 0) return 'Just now'
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
  }

  // Handle manual snapshot download
  const handleDownloadSnapshot = async () => {
    if (currentFrameUrl) {
      const a = document.createElement('a')
      a.href = currentFrameUrl
      a.download = `snapshot_${camera.camera_code}_${Date.now()}.jpg`
      a.click()
    } else {
      const snapUrl = await takeSnapshot()
      if (snapUrl) {
        const a = document.createElement('a')
        a.href = snapUrl
        a.download = `snapshot_${camera.camera_code}_${Date.now()}.jpg`
        a.click()
      }
    }
  }

  return (
    <div
      ref={tileRef}
      onClick={onSelect}
      className={cn(
        'group relative flex flex-col rounded-xl border bg-[#0b0f17] overflow-hidden transition-all duration-200 shadow-lg',
        isSelected
          ? 'border-cyan-500 shadow-cyan-500/10 ring-1 ring-cyan-500'
          : 'border-[#1e2633] hover:border-slate-700'
      )}
    >
      {/* Tile Header Bar */}
      <div className="flex h-10 items-center justify-between border-b border-[#1e2633] bg-[#0e1420] px-3 z-30">
        <div className="flex items-center gap-2 overflow-hidden">
          <span
            className={cn(
              'h-2 w-2 rounded-full shrink-0',
              camera.connection_status === 'online'
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                : camera.connection_status === 'degraded'
                ? 'bg-amber-400'
                : 'bg-rose-500'
            )}
          />
          <span className="font-mono text-xs font-bold text-slate-100 truncate">
            {camera.camera_code}
          </span>
          <span className="text-[11px] text-slate-400 truncate max-w-[120px]" title={camera.name}>
            {camera.name}
          </span>
          {locationName && (
            <span className="hidden sm:inline-block rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-300">
              {locationName}
            </span>
          )}
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Connection Status Pill */}
          <span
            className={cn(
              'flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border',
              statusColor
            )}
          >
            {camera.connection_status === 'online' ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            {camera.connection_status}
          </span>

          {/* Remove Tile Button */}
          {onRemove && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
              className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
              title="Remove camera from grid"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Video Viewport Container */}
      <div className="relative aspect-video w-full bg-black overflow-hidden flex items-center justify-center select-none">
        {/* Render Frame if available */}
        {currentFrameUrl ? (
          <img
            src={currentFrameUrl}
            alt={camera.name}
            className="w-full h-full object-contain"
          />
        ) : null}

        {/* SVG Overlays */}
        {currentFrameUrl && (
          <>
            <PolygonOverlay
              zones={cameraZones}
              occupancyStatus={occupancyStatus}
              visible={showPolygons}
            />
            <DetectionOverlay
              events={recentEvents}
              visible={showDetections}
            />
          </>
        )}

        {/* Loading State */}
        {isStreamLoading && !currentFrameUrl && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 text-slate-300 gap-3 z-20">
            <RefreshCw className="h-7 w-7 animate-spin text-cyan-400" />
            <div className="text-center">
              <p className="text-xs font-semibold text-slate-200">Connecting to Edge Stream</p>
              <p className="text-[11px] text-slate-400">Authenticating session & negotiating MJPEG...</p>
            </div>
          </div>
        )}

        {/* Offline / Deactivated / Error State */}
        {(!camera.is_active || streamError) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/95 text-slate-300 p-4 text-center z-20">
            <div className="p-3 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 mb-2">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <p className="text-xs font-bold text-slate-100">
              {!camera.is_active ? 'Camera Deactivated' : 'Stream Offline'}
            </p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-[260px] line-clamp-2">
              {!camera.is_active
                ? 'This camera has been deactivated. Activate camera in management settings to enable streaming.'
                : streamError}
            </p>

            {/* Error Code Specific Hint */}
            {streamErrorCode === 429 && (
              <p className="text-[10px] text-amber-400 mt-1 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                Concurrency limit reached. Other viewers must disconnect.
              </p>
            )}

            {camera.is_active && (
              <div className="flex items-center gap-2 mt-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    reconnect()
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-cyan-600 hover:bg-cyan-500 text-white transition-colors"
                >
                  <RefreshCw className="h-3 w-3" />
                  Retry Connection
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    takeSnapshot()
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
                >
                  <CameraIcon className="h-3 w-3" />
                  Snapshot
                </button>
              </div>
            )}
          </div>
        )}

        {/* Live HUD Floating Indicators */}
        {isStreaming && (
          <div className="absolute top-2 left-2 flex items-center gap-1.5 pointer-events-none z-30">
            {/* Live Rec Pill */}
            <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider bg-rose-600/90 text-white shadow-sm backdrop-blur-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
              LIVE
            </span>

            {/* Measured FPS */}
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-900/80 text-cyan-300 border border-slate-700/60 backdrop-blur-sm">
              {fps} FPS
            </span>
          </div>
        )}

        {/* Bottom Floating Control Bar (Appears on Hover) */}
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-30 pointer-events-auto">
          {/* Left overlays toggles */}
          <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-700/80 rounded-lg p-1 backdrop-blur-md">
            {/* Toggle Polygons */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                setShowPolygons(!showPolygons)
              }}
              className={cn(
                'p-1.5 rounded transition-colors text-xs flex items-center gap-1',
                showPolygons
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              )}
              title="Toggle Workstation Polygons"
            >
              <Layers className="h-3.5 w-3.5" />
              <span className="text-[10px] font-medium hidden sm:inline">Zones</span>
            </button>

            {/* Toggle Detections */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                setShowDetections(!showDetections)
              }}
              className={cn(
                'p-1.5 rounded transition-colors text-xs flex items-center gap-1',
                showDetections
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              )}
              title="Toggle AI Detection Overlays"
            >
              <Activity className="h-3.5 w-3.5" />
              <span className="text-[10px] font-medium hidden sm:inline">AI BBoxes</span>
            </button>
          </div>

          {/* Right tool buttons */}
          <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-700/80 rounded-lg p-1 backdrop-blur-md">
            {/* Take Snapshot */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDownloadSnapshot()
              }}
              className="p-1.5 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              title="Save Snapshot"
            >
              <Download className="h-3.5 w-3.5" />
            </button>

            {/* Reconnect / Refresh */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                reconnect()
              }}
              className="p-1.5 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              title="Reconnect Stream"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>

            {/* Fullscreen Tile */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                toggleFullscreen()
              }}
              className="p-1.5 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Tile'}
            >
              {isFullscreen ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Tile Footer Telemetry Bar */}
      <div className="flex h-7 items-center justify-between border-t border-[#1e2633] bg-[#0c1017] px-3 text-[11px] text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1" title="Last Heartbeat from Edge">
            <Clock className="h-3 w-3 text-slate-500" />
            {formatHeartbeat(camera.last_heartbeat_at)}
          </span>
          <span className="hidden sm:inline font-mono text-[10px] text-slate-500">
            {camera.stream_type.toUpperCase()}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {totalFrames > 0 && (
            <span className="font-mono text-[10px] text-slate-500">
              {totalFrames.toLocaleString()} frames
            </span>
          )}
          {cameraZones.length > 0 && (
            <span className="text-[10px] text-cyan-400/90 font-medium">
              {cameraZones.length} {cameraZones.length === 1 ? 'zone' : 'zones'}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
