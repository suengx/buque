import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { serve } from 'h3-v2'
import tanstack from '../dist/server/server.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const clientRoot = path.resolve(__dirname, '../dist/client')

const MIME = {
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

async function serveClientFile(pathname) {
  const rel = decodeURIComponent(pathname.replace(/^\//, ''))
  if (!rel || rel.includes('..')) return null

  const filePath = path.resolve(clientRoot, rel)
  if (!filePath.startsWith(clientRoot + path.sep)) return null

  try {
    const data = await readFile(filePath)
    const ext = path.extname(filePath)
    return new Response(data, {
      headers: { 'Content-Type': MIME[ext] ?? 'application/octet-stream' },
    })
  } catch {
    return null
  }
}

const app = {
  async fetch(request) {
    const staticRes = await serveClientFile(new URL(request.url).pathname)
    if (staticRes) return staticRes
    return tanstack.fetch(request)
  },
}

const port = Number(process.env.PORT || 3000)
serve(app, { port, hostname: '0.0.0.0' })
