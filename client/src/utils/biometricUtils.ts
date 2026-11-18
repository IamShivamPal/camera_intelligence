/**
 * Biometric utilities for AuraFace v1 512D embedding calculations and image validations.
 * Enforces strict L2 normalization and schema requirements:
 * - Vector dimension: exactly 512
 * - Values: finite floating point numbers
 * - L2 Norm: sqrt(sum(x_i^2)) in [0.95, 1.05]
 */

export function generateCalibratedUnitVector(seedString: string = 'default'): number[] {
  // Generate deterministic pseudo-random seed from string
  let hash = 0
  for (let i = 0; i < seedString.length; i++) {
    hash = (hash << 5) - hash + seedString.charCodeAt(i)
    hash |= 0
  }
  const seed = Math.abs(hash) + 1

  const dim = 512
  const raw: number[] = new Array(dim)
  let normSq = 0

  for (let i = 0; i < dim; i++) {
    // Generate sinusoidal pseudo-features
    const val = Math.sin(i * 0.17 + (seed % 997)) * Math.cos(i * 0.31 + (seed % 103))
    raw[i] = val
    normSq += val * val
  }

  const norm = Math.sqrt(normSq)
  if (norm < 1e-6) {
    // Fallback unit vector along first axis
    const unit = new Array(dim).fill(0)
    unit[0] = 1.0
    return unit
  }

  // L2 normalization: vector / norm
  return raw.map((x) => x / norm)
}

export function validateVectorL2Norm(vector: number[]): { isValid: boolean; norm: number } {
  if (!vector || vector.length !== 512) {
    return { isValid: false, norm: 0 }
  }

  let sumSq = 0
  for (let i = 0; i < 512; i++) {
    const val = vector[i]
    if (isNaN(val) || !isFinite(val)) {
      return { isValid: false, norm: 0 }
    }
    sumSq += val * val
  }

  const norm = Math.sqrt(sumSq)
  const isValid = norm >= 0.95 && norm <= 1.05
  return { isValid, norm }
}

export const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024 // 5MB
