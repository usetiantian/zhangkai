// 把 AI 产出的官方 H3 分镜解析成导演台 segments_json 数组。
// 复用导演台前端自己的解析函数，保证和插件行为一致。
// 用法: 读 stdin JSON {"storyboard": "...", "original_input": "..."}，输出 JSON。
import fs from 'node:fs'
import { loadContext } from './h3_js.mjs'

const { ctx } = await loadContext(['prepareOfficialStoryboardOutput', 'parseOfficialScript'])

const raw = fs.readFileSync(0, 'utf8')
let payload = {}
try {
  payload = JSON.parse(raw || '{}')
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: 'stdin 不是合法 JSON: ' + e.message }))
  process.exit(0)
}

const storyboard = String(payload.storyboard || '')
const originalInput = String(payload.original_input || '')
const seedBase = Number(payload.seed || 0) || 0

if (payload.mode === 'duration') {
  // 只为量跨度，跳过 prepare 的守恒门禁（门禁正是我们要绕过的）
  const p2 = ctx.parseOfficialScript(storyboard)
  if (!p2 || !p2.length) {
    process.stdout.write(JSON.stringify({ ok: false, error: '解析不到分段' }))
    process.exit(0)
  }
  const c2 = ctx.evaluateDurationConservation(p2.sourceDuration, p2)
  process.stdout.write(JSON.stringify({
    ok: true,
    source_duration: p2.sourceDuration,
    imported_duration: c2.importedDuration,
    ratio: c2.ratio,
    drift: c2.drift,
  }))
  process.exit(0)
}

const prep = ctx.prepareOfficialStoryboardOutput(storyboard, originalInput)
if (!prep.ok) {
  process.stdout.write(JSON.stringify({ ok: false, error: prep.error, repair_prompt: prep.repairPrompt || '' }))
  process.exit(0)
}

const parsed = ctx.parseOfficialScript(prep.content)
if (!parsed || !parsed.length) {
  process.stdout.write(JSON.stringify({ ok: false, error: '分镜解析后没有分段' }))
  process.exit(0)
}

const segments = parsed.map((seg, index) => ({
  prompt: seg.prompt,
  seed: (seedBase + index * 1000003) % 2147483647,
  refs: [],
  video_refs: [],
  duration: seg.duration,
  enabled: true,
  inherit_shared: true,
}))

process.stdout.write(JSON.stringify({
  ok: true,
  note: prep.note || '',
  source_duration: parsed.sourceDuration,
  official: parsed.official,
  warnings: parsed.warnings || [],
  segments,
}))
