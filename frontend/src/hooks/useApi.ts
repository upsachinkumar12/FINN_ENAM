import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../services/api'

/** Fetch a GET endpoint. On refetch the previous data stays on screen (no skeleton flash). */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(!!path)
  const seq = useRef(0)

  const load = useCallback(async () => {
    if (!path) return
    const mine = ++seq.current
    setLoading(true)
    try {
      const d = await api.get<T>(path)
      if (mine === seq.current) {
        setData(d)
        setError(null)
      }
    } catch (e) {
      if (mine === seq.current) setError((e as Error).message)
    } finally {
      if (mine === seq.current) setLoading(false)
    }
  }, [path])

  useEffect(() => {
    void load()
  }, [load])

  return { data, error, loading, reload: load, setData }
}
