import React from 'react'
import type { WorkstationZone } from '@/types/api'

interface PolygonOverlayProps {
  zones: WorkstationZone[]
  occupancyStatus?: Record<number, { state: 'active' | 'idle' | 'vacant'; employeeName?: string }>
  visible?: boolean
}

export const PolygonOverlay: React.FC<PolygonOverlayProps> = ({
  zones,
  occupancyStatus = {},
  visible = true,
}) => {
  if (!visible || !zones || zones.length === 0) return null

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none select-none z-10"
      viewBox="0 0 1000 562.5"
      preserveAspectRatio="none"
    >
      <defs>
        {/* Glow Filters */}
        <filter id="zone-glow-active" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#10b981" floodOpacity="0.8" />
        </filter>
        <filter id="zone-glow-idle" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#f59e0b" floodOpacity="0.8" />
        </filter>
        <filter id="zone-glow-default" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#06b6d4" floodOpacity="0.6" />
        </filter>
      </defs>

      {zones.map((zone) => {
        if (!zone.polygon_points || zone.polygon_points.length < 3) return null

        // Convert normalized [nx, ny] (0..1) to SVG 1000x562.5 coordinates
        const pointsString = zone.polygon_points
          .map(([nx, ny]) => `${nx * 1000},${ny * 562.5}`)
          .join(' ')

        // Calculate centroid for label
        const sumX = zone.polygon_points.reduce((acc, [nx]) => acc + nx * 1000, 0)
        const sumY = zone.polygon_points.reduce((acc, [, ny]) => acc + ny * 562.5, 0)
        const centroidX = sumX / zone.polygon_points.length
        const centroidY = sumY / zone.polygon_points.length

        // Check genuine occupancy status if reported by recent backend events
        const occupancy = occupancyStatus[zone.id]
        let strokeColor = '#06b6d4' // Cyan default
        let fillColor = 'rgba(6, 182, 212, 0.15)'
        let filter = 'url(#zone-glow-default)'
        let statusBadge = 'Configured'

        if (occupancy?.state === 'active') {
          strokeColor = '#10b981' // Emerald
          fillColor = 'rgba(16, 185, 129, 0.25)'
          filter = 'url(#zone-glow-active)'
          statusBadge = occupancy.employeeName ? `Active: ${occupancy.employeeName}` : 'Active'
        } else if (occupancy?.state === 'idle') {
          strokeColor = '#f59e0b' // Amber
          fillColor = 'rgba(245, 158, 11, 0.25)'
          filter = 'url(#zone-glow-idle)'
          statusBadge = 'Idle / Exceeded'
        }

        return (
          <g key={zone.id} className="transition-all duration-300">
            {/* Polygon Boundary */}
            <polygon
              points={pointsString}
              stroke={strokeColor}
              strokeWidth="2.5"
              fill={fillColor}
              strokeDasharray={occupancy?.state ? 'none' : '4 2'}
              filter={filter}
            />

            {/* Polygon Vertex Markers */}
            {zone.polygon_points.map(([nx, ny], idx) => (
              <circle
                key={idx}
                cx={nx * 1000}
                cy={ny * 562.5}
                r="3"
                fill={strokeColor}
                stroke="#ffffff"
                strokeWidth="1"
              />
            ))}

            {/* Centroid Tag */}
            <g transform={`translate(${centroidX}, ${centroidY})`}>
              <rect
                x="-55"
                y="-18"
                width="110"
                height="36"
                rx="5"
                fill="rgba(15, 23, 42, 0.85)"
                stroke={strokeColor}
                strokeWidth="1"
              />
              <text
                x="0"
                y="-4"
                textAnchor="middle"
                fill="#f8fafc"
                fontSize="11"
                fontWeight="bold"
                fontFamily="sans-serif"
              >
                {zone.zone_code}
              </text>
              <text
                x="0"
                y="10"
                textAnchor="middle"
                fill={strokeColor}
                fontSize="9"
                fontWeight="600"
                fontFamily="sans-serif"
              >
                {statusBadge}
              </text>
            </g>
          </g>
        )
      })}
    </svg>
  )
}
