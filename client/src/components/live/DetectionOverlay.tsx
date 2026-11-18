import React from 'react'
import type { DetectionEvent } from '@/types/api'

interface DetectionOverlayProps {
  events: DetectionEvent[]
  visible?: boolean
}

export const DetectionOverlay: React.FC<DetectionOverlayProps> = ({
  events,
  visible = true,
}) => {
  if (!visible) return null

  // Extract events that contain valid bounding boxes
  const eventsWithBbox = events.filter((e) => {
    const bbox = e.metadata_json?.bbox
    return Array.isArray(bbox) && bbox.length === 4
  })

  // If no bounding boxes in recent events, render no fabricated boxes
  if (eventsWithBbox.length === 0) {
    return (
      <div className="absolute top-2 right-2 pointer-events-none z-10">
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900/80 text-slate-400 border border-slate-700/60 backdrop-blur-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
          No live bboxes
        </span>
      </div>
    )
  }

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none select-none z-20"
      viewBox="0 0 1000 562.5"
      preserveAspectRatio="none"
    >
      <defs>
        <filter id="box-glow-person" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#38bdf8" floodOpacity="0.7" />
        </filter>
        <filter id="box-glow-employee" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#10b981" floodOpacity="0.8" />
        </filter>
        <filter id="box-glow-alert" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#f43f5e" floodOpacity="0.8" />
        </filter>
      </defs>

      {eventsWithBbox.map((event) => {
        const bbox = event.metadata_json!.bbox as [number, number, number, number]
        let [x1, y1, x2, y2] = bbox

        // Normalize coordinates to 1000x562.5 viewBox
        // If values are <= 1.0, they are already normalized
        if (x1 <= 1.0 && x2 <= 1.0 && y1 <= 1.0 && y2 <= 1.0) {
          x1 = x1 * 1000
          y1 = y1 * 562.5
          x2 = x2 * 1000
          y2 = y2 * 562.5
        } else {
          // If values are pixel coords (e.g. 1920x1080 or 1280x720)
          // Default mapping based on standard 1080p source frame
          const scaleX = 1000 / 1920
          const scaleY = 562.5 / 1080
          x1 = x1 * scaleX
          y1 = y1 * scaleY
          x2 = x2 * scaleX
          y2 = y2 * scaleY
        }

        const width = Math.max(20, x2 - x1)
        const height = Math.max(20, y2 - y1)

        // Determine badge styling based on genuine event data
        const isRecognized = event.event_type === 'employee_recognized' || !!event.employee_id
        const isIntrusion = event.event_type === 'after_hours_intrusion'

        let strokeColor = '#38bdf8' // Blue/Sky default
        let filter = 'url(#box-glow-person)'
        let label = 'Unknown Person'

        if (isRecognized) {
          strokeColor = '#10b981' // Green
          filter = 'url(#box-glow-employee)'
          label = event.employee_id ? `Employee #${event.employee_id}` : 'Employee'
        } else if (isIntrusion) {
          strokeColor = '#f43f5e' // Rose
          filter = 'url(#box-glow-alert)'
          label = 'Security Alert'
        }

        const confidenceText = event.confidence
          ? `${Math.round(event.confidence * 100)}%`
          : event.metadata_json?.detector_conf
          ? `${Math.round(event.metadata_json.detector_conf * 100)}%`
          : null

        const trackerText = event.tracker_id ? `#${event.tracker_id}` : null

        return (
          <g key={event.id} className="transition-all duration-200">
            {/* Detection Bounding Box */}
            <rect
              x={x1}
              y={y1}
              width={width}
              height={height}
              fill="rgba(56, 189, 248, 0.08)"
              stroke={strokeColor}
              strokeWidth="2"
              rx="4"
              filter={filter}
            />

            {/* Corner Bracket Accents */}
            <line x1={x1} y1={y1} x2={x1 + 10} y2={y1} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x1} y1={y1} x2={x1} y2={y1 + 10} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x2} y1={y1} x2={x2 - 10} y2={y1} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x2} y1={y1} x2={x2} y2={y1 + 10} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x1} y1={y2} x2={x1 + 10} y2={y2} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x1} y1={y2} x2={x1} y2={y2 - 10} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x2} y1={y2} x2={x2 - 10} y2={y2} stroke="#ffffff" strokeWidth="2.5" />
            <line x1={x2} y1={y2} x2={x2} y2={y2 - 10} stroke="#ffffff" strokeWidth="2.5" />

            {/* Telemetry Header Pill */}
            <g transform={`translate(${x1}, ${Math.max(16, y1 - 18)})`}>
              <rect
                x="0"
                y="0"
                width={Math.min(180, Math.max(100, label.length * 7 + 35))}
                height="16"
                rx="3"
                fill="rgba(15, 23, 42, 0.9)"
                stroke={strokeColor}
                strokeWidth="1"
              />
              <text
                x="6"
                y="11.5"
                fill="#ffffff"
                fontSize="9"
                fontWeight="bold"
                fontFamily="sans-serif"
              >
                {label} {confidenceText ? `(${confidenceText})` : ''}
              </text>
            </g>

            {/* Tracking ID Bottom Pill */}
            {trackerText && (
              <g transform={`translate(${x1}, ${y2 + 4})`}>
                <rect
                  x="0"
                  y="0"
                  width="55"
                  height="14"
                  rx="3"
                  fill="rgba(15, 23, 42, 0.85)"
                  stroke={strokeColor}
                  strokeWidth="0.8"
                />
                <text
                  x="6"
                  y="10"
                  fill="#94a3b8"
                  fontSize="8"
                  fontWeight="600"
                  fontFamily="sans-serif"
                >
                  {trackerText}
                </text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
