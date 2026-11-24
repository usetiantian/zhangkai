// 取出导演台的系统提示词（复用插件里的构造函数，避免自己重写导致漂移）。
// 用法: node tools/h3_prompts.mjs <mode> [assetContext]
//   mode: script | storyboard | create_script | create_storyboard
import { loadContext } from './h3_js.mjs'

const { ctx } = await loadContext([
  'buildStoryToScriptSys', 'buildOfficialStoryboardSys',
  'buildCreateStoryToScriptSys', 'buildCreateOfficialStoryboardSys',
])

const mode = process.argv[2] || 'script'
const assetContext = process.argv[3] || '（参考资产库为空）'
let out = ''
if (mode === 'script') out = ctx.buildStoryToScriptSys(assetContext, 'zh-CN')
else if (mode === 'storyboard') out = ctx.buildOfficialStoryboardSys(assetContext, 'zh-CN')
else if (mode === 'create_script') out = ctx.buildCreateStoryToScriptSys(assetContext)
else if (mode === 'create_storyboard') out = ctx.buildCreateOfficialStoryboardSys(assetContext)
else throw new Error('未知 mode: ' + mode)
process.stdout.write(out)
