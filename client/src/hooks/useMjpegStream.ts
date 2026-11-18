import { useState, useEffect, useRef, useCallback } from 'react'
import { cameraService } from '@/services/cameraService'

export interface MjpegStreamOptions {
  cameraId: number | null
  token: string | null
  enabled?: boolean
  fps?: number
  quality?: number
}

export interface MjpegStreamState {
  currentFrameUrl: string | null
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  errorCode: number | null
  fps: number
  totalFrames: number
  lastFrameTimestamp: number | null
  reconnect: () => void
  takeSnapshot: () => Promise<string | null>
}

// Marker bytes for JPEG standard
const SOI = [0xff, 0xd8]
const EOI = [0xff, 0xd9]

export function useMjpegStream({
  cameraId,
  token,
  enabled = true,
  fps = 15,
  quality = 75,
}: MjpegStreamOptions): MjpegStreamState {
  const [currentFrameUrl, setCurrentFrameUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isStreaming, setIsStreaming] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<number | null>(null)
  const [measuredFps, setMeasuredFps] = useState<number>(0)
  const [totalFrames, setTotalFrames] = useState<number>(0)
  const [lastFrameTimestamp, setLastFrameTimestamp] = useState<number | null>(null)

  // Track retry count and manual reload trigger
  const [retryTrigger, setRetryTrigger] = useState<number>(0)

  // Object URL cleanup ref to prevent memory leak
  const prevUrlRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // FPS measurement counters
  const frameCountWindowRef = useRef<number>(0)
  const lastFpsCalcTimeRef = useRef<number>(0)

  const cleanupUrls = useCallback(() => {
    if (prevUrlRef.current) {
      URL.revokeObjectURL(prevUrlRef.current)
      prevUrlRef.current = null
    }
  }, [])

  const reconnect = useCallback(() => {
    cleanupUrls()
    setError(null)
    setErrorCode(null)
    setCurrentFrameUrl(null)
    setRetryTrigger((prev) => prev + 1)
  }, [cleanupUrls])

  const takeSnapshot = useCallback(async (): Promise<string | null> => {
    if (!cameraId) return null
    try {
      const blob = await cameraService.getSnapshot(cameraId, quality)
      const url = URL.createObjectURL(blob)
      cleanupUrls()
      prevUrlRef.current = url
      setCurrentFrameUrl(url)
      setLastFrameTimestamp(Date.now())
      return url
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Snapshot capture failed'
      setError(message)
      return null
    }
  }, [cameraId, quality, cleanupUrls])

  useEffect(() => {
    // If no camera or token, or disabled, abort any active stream
    if (!cameraId || !token || !enabled) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
      return
    }

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    frameCountWindowRef.current = 0
    lastFpsCalcTimeRef.current = performance.now()

    const streamUrl = cameraService.getStreamUrl(cameraId, fps, quality)

    async function startStream() {
      setIsLoading(true)
      setIsStreaming(false)
      setError(null)
      setErrorCode(null)
      setMeasuredFps(0)

      try {
        const response = await fetch(streamUrl, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'multipart/x-mixed-replace',
          },
          signal: abortController.signal,
        })

        if (!response.ok) {
          setErrorCode(response.status)
          let errorDetail = `Stream error: HTTP ${response.status}`
          try {
            const errorJson = await response.json()
            if (errorJson.detail) {
              errorDetail = errorJson.detail
            }
          } catch {
            if (response.status === 403) {
              errorDetail = 'Access denied: Unauthorized for this location.'
            } else if (response.status === 404) {
              errorDetail = 'Camera not found or deactivated.'
            } else if (response.status === 429) {
              errorDetail = 'Viewer limit exceeded: Maximum concurrent viewers reached.'
            } else if (response.status === 503) {
              errorDetail = 'Camera offline: Edge Ingestion Service is unreachable.'
            }
          }
          setError(errorDetail)
          setIsLoading(false)
          setIsStreaming(false)
          return
        }

        if (!response.body) {
          setError('Response body is empty or stream not supported by browser.')
          setIsLoading(false)
          return
        }

        const reader = response.body.getReader()
        let buffer = new Uint8Array(0)
        let firstFrameReceived = false

        while (!abortController.signal.aborted) {
          const { done, value } = await reader.read()
          if (done) break

          if (value) {
            // Concat incoming value into buffer
            const newBuffer = new Uint8Array(buffer.length + value.length)
            newBuffer.set(buffer)
            newBuffer.set(value, buffer.length)
            buffer = newBuffer

            // Find SOI (0xFF, 0xD8) and EOI (0xFF, 0xD9)
            while (buffer.length > 4) {
              // Locate SOI
              let soiIdx = -1
              for (let i = 0; i < buffer.length - 1; i++) {
                if (buffer[i] === SOI[0] && buffer[i + 1] === SOI[1]) {
                  soiIdx = i
                  break
                }
              }

              if (soiIdx === -1) {
                // Keep only last byte in case SOI is split across chunks
                buffer = buffer.slice(buffer.length - 1)
                break
              }

              // Locate EOI after SOI
              let eoiIdx = -1
              for (let i = soiIdx + 2; i < buffer.length - 1; i++) {
                if (buffer[i] === EOI[0] && buffer[i + 1] === EOI[1]) {
                  eoiIdx = i + 2
                  break
                }
              }

              if (eoiIdx === -1) {
                // Frame still incomplete, keep from soiIdx onward
                if (soiIdx > 0) {
                  buffer = buffer.slice(soiIdx)
                }
                // Guard against buffer unbounded growth on corrupted streams
                if (buffer.length > 5 * 1024 * 1024) {
                  buffer = new Uint8Array(0)
                }
                break
              }

              // Complete JPEG frame found
              const frameBytes = buffer.subarray(soiIdx, eoiIdx)
              buffer = buffer.slice(eoiIdx)

              // Create frame blob and object URL
              const blob = new Blob([frameBytes], { type: 'image/jpeg' })
              const frameUrl = URL.createObjectURL(blob)

              // Revoke previous URL to prevent memory leaks
              if (prevUrlRef.current) {
                URL.revokeObjectURL(prevUrlRef.current)
              }
              prevUrlRef.current = frameUrl

              setCurrentFrameUrl(frameUrl)
              setLastFrameTimestamp(Date.now())
              setTotalFrames((prev) => prev + 1)

              if (!firstFrameReceived) {
                firstFrameReceived = true
                setIsLoading(false)
                setIsStreaming(true)
              }

              // Track FPS
              frameCountWindowRef.current += 1
              const now = performance.now()
              const elapsed = now - lastFpsCalcTimeRef.current
              if (elapsed >= 1000) {
                const currentFps = Math.round((frameCountWindowRef.current * 1000) / elapsed)
                setMeasuredFps(currentFps)
                frameCountWindowRef.current = 0
                lastFpsCalcTimeRef.current = now
              }
            }
          }
        }
      } catch (err: any) {
        if (abortController.signal.aborted) {
          // Normal teardown / unmount
          return
        }
        setError(err.message || 'Stream interrupted or network connection dropped')
        setIsLoading(false)
        setIsStreaming(false)
      } finally {
        setIsLoading(false)
      }
    }

    startStream()

    return () => {
      abortController.abort()
      cleanupUrls()
    }
  }, [cameraId, token, enabled, fps, quality, retryTrigger, cleanupUrls])

  const effectiveIsLoading = Boolean(cameraId && token && enabled) && isLoading
  const effectiveIsStreaming = Boolean(cameraId && token && enabled) && isStreaming

  return {
    currentFrameUrl,
    isLoading: effectiveIsLoading,
    isStreaming: effectiveIsStreaming,
    error,
    errorCode,
    fps: measuredFps,
    totalFrames,
    lastFrameTimestamp,
    reconnect,
    takeSnapshot,
  }
}
