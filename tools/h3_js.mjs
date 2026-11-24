// 从导演台前端按依赖闭包抽取纯函数，供无头流水线复用。
// 避免自己重写一套分镜解析逻辑（会跟插件漂移）。
// 注意：本文件刻意不含反斜杠（shell heredoc 会吃掉它们）。
import fs from 'node:fs'
import vm from 'node:vm'

export const JS_DIR =
  'D:/ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-H3-Director/web/js'
export const JS_PATH = JS_DIR + '/h3_studio.js'
export const TOOLS_PATH = JS_DIR + '/h3_script_tools.js'

const SRC = fs.readFileSync(JS_PATH, 'utf8')
const NL = String.fromCharCode(10)

function isIdent(ch) {
  if (!ch) return false
  const c = ch.charCodeAt(0)
  return (c >= 97 && c <= 122) || (c >= 65 && c <= 90) ||
         (c >= 48 && c <= 57) || ch === '_' || ch === '$'
}

function isSpace(ch) {
  return ch === ' ' || ch === String.fromCharCode(9) || ch === NL || ch === String.fromCharCode(13)
}

// 顶层 function 定义 -> {name, start, end}
const FUNCS = new Map()
{
  let i = 0
  while (true) {
    const at = SRC.indexOf('function ', i)
    if (at < 0) break
    i = at + 9
    const lineStart = SRC.lastIndexOf(NL, at) + 1
    let onlySpace = true
    for (let k = lineStart; k < at; k++) {
      if (!isSpace(SRC[k])) { onlySpace = false; break }
    }
    if (!onlySpace) continue
    let j = at + 9
    while (j < SRC.length && isSpace(SRC[j])) j++
    let k = j
    while (k < SRC.length && isIdent(SRC[k])) k++
    const name = SRC.slice(j, k)
    if (!name) continue
    const b = SRC.indexOf('{', k)
    if (b < 0) continue
    let depth = 0
    let p = b
    for (; p < SRC.length; p++) {
      const ch = SRC[p]
      if (ch === '{') depth++
      else if (ch === '}') { depth--; if (depth === 0) { p++; break } }
    }
    if (!FUNCS.has(name)) FUNCS.set(name, { name, start: at, end: p })
  }
}

function bodyOf(name) {
  const f = FUNCS.get(name)
  return f ? SRC.slice(f.start, f.end) : ''
}

function refsIn(name) {
  const body = bodyOf(name)
  const out = new Set()
  const tokens = body.split(/[^A-Za-z0-9_$]+/)
  for (const tok of tokens) {
    if (tok && tok !== name && FUNCS.has(tok)) out.add(tok)
  }
  return out
}

// h3_script_tools.js 是无 DOM 的纯 ES 模块，直接 import 复用
let TOOLS = {}
try {
  TOOLS = await import('file:///' + TOOLS_PATH)
} catch (e) {
  console.error('加载 h3_script_tools.js 失败:', e.message)
}

export async function loadContext(seeds) {
  const wanted = new Set()
  const queue = [...seeds]
  while (queue.length) {
    const name = queue.shift()
    if (!name || wanted.has(name) || !FUNCS.has(name)) continue
    wanted.add(name)
    for (const r of refsIn(name)) if (!wanted.has(r)) queue.push(r)
  }
  const code = [...wanted]
    .map((n) => SRC.slice(FUNCS.get(n).start, FUNCS.get(n).end))
    .join(NL + NL)
  const ctx = { console }
  ctx.globalThis = ctx
  for (const key of Object.keys(TOOLS)) ctx[key] = TOOLS[key]
  vm.createContext(ctx)
  vm.runInContext(code, ctx, { filename: 'h3_studio_extracted.js' })
  return { ctx, names: [...wanted] }
}
