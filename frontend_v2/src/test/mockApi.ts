/**
 * Minimal fetch stub for tests - no extra dependencies.
 * Handlers receive (method, url) and return a Response-like object or throw.
 */
export type RouteHandler = (ctx: {
  method: string
  url: URL
  body: any
}) => { status?: number; json?: unknown } | undefined

export class FetchMock {
  calls: { method: string; path: string; body?: any }[] = []
  private handler: RouteHandler

  constructor(handler: RouteHandler) {
    this.handler = handler
  }

  install() {
    const self = this
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL, init?: RequestInit) => {
        const url = new URL(String(input), 'http://localtest')
        const method = (init?.method ?? 'GET').toUpperCase()
        let body: any
        if (init?.body) {
          try {
            body = JSON.parse(String(init.body))
          } catch {
            body = String(init.body)
          }
        }
        self.calls.push({ method, path: url.pathname + url.search, body })
        const result = (await self.handler({ method, url, body })) ?? undefined
        if (!result) {
          return new Response(JSON.stringify({ detail: 'not mocked' }), {
            status: 404,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        const status = result.status ?? 200
        if (status === 204) return new Response(null, { status })
        return new Response(JSON.stringify(result.json), {
          status,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )
  }

  callsFor(path: string) {
    return this.calls.filter((c) => c.path === path || c.path.startsWith(path + '?'))
  }
}

export function jsonOk(json: unknown) {
  return { status: 200, json }
}

export function jsonError(status: number, detail: string) {
  return { status, json: { detail } }
}
