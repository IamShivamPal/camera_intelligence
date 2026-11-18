import React, { useState, useRef, useCallback } from 'react'
import {
  RotateCcw,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Maximize2,
  Info,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface PolygonEditorCanvasProps {
  points: [number, number][]
  onChange: (points: [number, number][]) => void
  readOnly?: boolean
}

const SVG_WIDTH = 1000
const SVG_HEIGHT = 562.5 // 16:9 standard CCTV frame aspect ratio

export const PolygonEditorCanvas: React.FC<PolygonEditorCanvasProps> = ({
  points,
  onChange,
  readOnly = false,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  // Presets
  const loadRectanglePreset = () => {
    onChange([
      [0.25, 0.3],
      [0.75, 0.3],
      [0.75, 0.8],
      [0.25, 0.8],
    ])
  }

  const loadTrapezoidPreset = () => {
    onChange([
      [0.3, 0.35],
      [0.7, 0.35],
      [0.85, 0.85],
      [0.15, 0.85],
    ])
  }

  const clearPoints = () => {
    onChange([])
  }

  // Convert normalized [nx, ny] to SVG coordinates
  const toSvgX = (nx: number) => nx * SVG_WIDTH
  const toSvgY = (ny: number) => ny * SVG_HEIGHT

  // Convert mouse event coordinates to normalized [0, 1]
  const getNormalizedCoords = useCallback(
    (e: React.MouseEvent<SVGSVGElement>): [number, number] | null => {
      if (!svgRef.current) return null
      const rect = svgRef.current.getBoundingClientRect()
      const rawX = (e.clientX - rect.left) / rect.width
      const rawY = (e.clientY - rect.top) / rect.height
      const clampedX = Math.max(0, Math.min(1, Math.round(rawX * 10000) / 10000))
      const clampedY = Math.max(0, Math.min(1, Math.round(rawY * 10000) / 10000))
      return [clampedX, clampedY]
    },
    []
  )

  // Handle clicking on canvas background to add point
  const handleCanvasClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (readOnly || draggedIndex !== null) return
    const coords = getNormalizedCoords(e)
    if (!coords) return
    onChange([...points, coords])
  }

  // Start dragging vertex
  const handleMouseDown = (index: number, e: React.MouseEvent) => {
    if (readOnly) return
    e.stopPropagation()
    setDraggedIndex(index)
  }

  // Dragging vertex
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (readOnly || draggedIndex === null) return
    const coords = getNormalizedCoords(e)
    if (!coords) return

    const updated = [...points]
    updated[draggedIndex] = coords
    onChange(updated as [number, number][])
  }

  // End dragging
  const handleMouseUp = () => {
    if (readOnly) return
    setDraggedIndex(null)
  }

  // Delete individual vertex
  const handleDeleteVertex = (index: number, e?: React.MouseEvent) => {
    if (readOnly) return
    if (e) e.stopPropagation()
    onChange(points.filter((_, i) => i !== index))
  }

  // Validation
  const hasAtLeastThreePoints = points.length >= 3
  const uniquePointsCount = new Set(
    points.map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`)
  ).size
  const isValidPolygon = hasAtLeastThreePoints && uniquePointsCount >= 3

  // Format SVG polygon points attribute string
  const polygonPointsStr = points.map(([x, y]) => `${toSvgX(x)},${toSvgY(y)}`).join(' ')

  return (
    <div className="space-y-3 font-mono text-xs">
      {/* Canvas Top Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1b2331] pb-2 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 font-bold text-slate-200">
            <Maximize2 className="h-3.5 w-3.5 text-cyan-400" />
            CALIBRATION CANVAS (16:9 PROJECTION)
          </span>
          <span
            className={cn(
              'rounded px-2 py-0.5 text-[9px] uppercase font-bold',
              isValidPolygon
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
            )}
          >
            {isValidPolygon ? `${points.length} VERTICES (VALID)` : `${points.length} VERTICES (MIN 3 REQUIRED)`}
          </span>
        </div>

        {!readOnly && (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={loadRectanglePreset}
              className="rounded border border-[#243044] bg-[#111722] px-2 py-1 text-[10px] text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
              title="Standard Desk Polygon"
            >
              Desk Preset
            </button>
            <button
              type="button"
              onClick={loadTrapezoidPreset}
              className="rounded border border-[#243044] bg-[#111722] px-2 py-1 text-[10px] text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
              title="Perspective / Angled Workstation"
            >
              Perspective Preset
            </button>
            <button
              type="button"
              onClick={clearPoints}
              className="rounded border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-[10px] text-rose-300 hover:bg-rose-500/20 transition-colors"
              title="Clear all points"
            >
              <RotateCcw className="h-3 w-3 inline mr-1" />
              Clear
            </button>
          </div>
        )}
      </div>

      {/* SVG Interactive Canvas */}
      <div className="relative w-full aspect-video rounded-lg border border-[#222d3f] bg-[#070a0f] overflow-hidden select-none shadow-inner">
        {/* Notice Watermark */}
        <div className="absolute top-2 left-3 pointer-events-none z-10 flex items-center gap-1.5 text-[10px] text-slate-500 font-mono">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span>STATIC CALIBRATION GRID &bull; NOT A LIVE CAMERA FEED &bull; [0.0, 1.0] NORMALIZED</span>
        </div>

        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className={cn('w-full h-full', !readOnly && 'cursor-crosshair')}
          onClick={handleCanvasClick}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Subdued Calibration Grid Lines */}
          <defs>
            <pattern id="calibGrid" width="100" height="56.25" patternUnits="userSpaceOnUse">
              <path
                d="M 100 0 L 0 0 0 56.25"
                fill="none"
                stroke="#131b26"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#calibGrid)" />

          {/* Center Crosshairs */}
          <line
            x1={SVG_WIDTH / 2}
            y1="0"
            x2={SVG_WIDTH / 2}
            y2={SVG_HEIGHT}
            stroke="#1b2535"
            strokeDasharray="4 4"
            strokeWidth="1"
          />
          <line
            x1="0"
            y1={SVG_HEIGHT / 2}
            x2={SVG_WIDTH}
            y2={SVG_HEIGHT / 2}
            stroke="#1b2535"
            strokeDasharray="4 4"
            strokeWidth="1"
          />

          {/* Polygon Fill & Boundary Strokes */}
          {points.length >= 2 && (
            <polygon
              points={polygonPointsStr}
              fill={isValidPolygon ? 'rgba(16, 185, 129, 0.22)' : 'rgba(245, 158, 11, 0.15)'}
              stroke={isValidPolygon ? '#10b981' : '#f59e0b'}
              strokeWidth="2.5"
              strokeDasharray={isValidPolygon ? undefined : '6 4'}
            />
          )}

          {/* Vertices and Interactive Handles */}
          {points.map(([nx, ny], idx) => {
            const sx = toSvgX(nx)
            const sy = toSvgY(ny)
            const isHovered = hoveredIndex === idx
            const isDragged = draggedIndex === idx

            return (
              <g
                key={idx}
                onMouseDown={(e) => handleMouseDown(idx, e)}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className={!readOnly ? 'cursor-grab active:cursor-grabbing' : undefined}
              >
                {/* Outer Glow Halo */}
                <circle
                  cx={sx}
                  cy={sy}
                  r={isHovered || isDragged ? 14 : 9}
                  fill={isDragged ? 'rgba(6, 182, 212, 0.4)' : 'rgba(16, 185, 129, 0.25)'}
                  className="transition-all"
                />

                {/* Central Point */}
                <circle
                  cx={sx}
                  cy={sy}
                  r={isHovered || isDragged ? 6 : 4.5}
                  fill={isDragged ? '#22d3ee' : '#10b981'}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />

                {/* Vertex Index Label */}
                <text
                  x={sx + 10}
                  y={sy - 10}
                  fill="#94a3b8"
                  fontSize="12"
                  fontFamily="monospace"
                  fontWeight="bold"
                >
                  V{idx + 1}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Empty Overlay when zero points */}
        {points.length === 0 && (
          <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center text-center p-4">
            <Plus className="h-8 w-8 text-slate-600 mb-1" />
            <p className="text-xs font-bold text-slate-300 font-mono">
              Click anywhere inside canvas to add polygon vertices
            </p>
            <p className="text-[10px] text-slate-500 font-mono mt-0.5">
              Define the boundary of the desk or workstation area monitored by the camera.
            </p>
          </div>
        )}
      </div>

      {/* Vertex Coordinates Inspector List */}
      <div className="rounded-lg border border-[#1e2633] bg-[#0c1017] p-3 space-y-2">
        <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-[#18202d] pb-1.5">
          <span className="font-bold text-slate-300 flex items-center gap-1">
            <Info className="h-3 w-3 text-cyan-400" />
            NORMALIZED VERTEX COORDINATES [0.0, 1.0]
          </span>
          <span className="text-[10px] text-slate-500">
            {points.length} points defined
          </span>
        </div>

        {points.length === 0 ? (
          <p className="text-[10px] text-slate-500 italic py-1">
            No vertices placed yet. Click the canvas or choose a preset above.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2 pt-1 max-h-28 overflow-y-auto">
            {points.map(([x, y], idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 rounded border border-[#222d3f] bg-[#111722] px-2 py-1 text-[10px] font-mono text-slate-300"
              >
                <span className="font-bold text-emerald-400">V{idx + 1}:</span>
                <span>
                  ({x.toFixed(4)}, {y.toFixed(4)})
                </span>
                {!readOnly && (
                  <button
                    type="button"
                    onClick={() => handleDeleteVertex(idx)}
                    className="ml-1 text-slate-500 hover:text-rose-400 transition-colors"
                    title={`Delete Vertex ${idx + 1}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {!isValidPolygon && points.length > 0 && (
          <div className="flex items-center gap-1.5 text-amber-400 text-[10px] pt-1 border-t border-[#18202d]">
            <AlertTriangle className="h-3 w-3 shrink-0" />
            <span>
              A valid workstation zone requires at least 3 distinct non-collinear vertices.
            </span>
          </div>
        )}

        {isValidPolygon && (
          <div className="flex items-center gap-1.5 text-emerald-400 text-[10px] pt-1 border-t border-[#18202d]">
            <CheckCircle2 className="h-3 w-3 shrink-0" />
            <span>
              Valid closed polygon geometry. Ready for AI Engine ray-casting containment.
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
