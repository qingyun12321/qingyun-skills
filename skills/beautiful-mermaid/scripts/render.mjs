#!/usr/bin/env node
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const PACKAGE_SPEC = 'beautiful-mermaid@1.1.3'
const SCRIPT_PATH = fileURLToPath(import.meta.url)
const SUPPORTED = [
  'graph TD|TB|LR|BT|RL',
  'flowchart TD|TB|LR|BT|RL',
  'stateDiagram or stateDiagram-v2',
  'sequenceDiagram',
  'classDiagram',
  'erDiagram',
  'xychart or xychart-beta',
]

function printHelp() {
  console.log(`Usage:
  render.mjs --format svg --input diagram.mmd --output diagram.svg [options]
  render.mjs --format ascii --input diagram.mmd [options]
  render.mjs --list-themes

Options:
  --format svg|ascii          Output format. Default: svg
  --input <file>              Read Mermaid source from file. Defaults to stdin
  --output <file>             Write output to file. Defaults to stdout
  --theme <name>              SVG theme name. Default: github-light
  --bg <color>                SVG background color override
  --fg <color>                SVG foreground color override
  --line <color>              SVG connector color override
  --accent <color>            SVG arrow/highlight color override
  --muted <color>             SVG secondary text color override
  --surface <color>           SVG node fill color override
  --border <color>            SVG node border color override
  --font <family>             SVG font family
  --transparent               Render SVG without a background fill
  --interactive               Enable xychart SVG tooltips
  --padding <number>          SVG canvas padding
  --node-spacing <number>     SVG sibling node spacing
  --layer-spacing <number>    SVG layer spacing
  --component-spacing <num>   SVG disconnected component spacing
  --ascii                     Use plain ASCII instead of Unicode box drawing
  --color-mode <mode>         none|auto|ansi16|ansi256|truecolor|html. Default: none
  --padding-x <number>        ASCII horizontal node spacing
  --padding-y <number>        ASCII vertical node spacing
  --box-border-padding <num>  ASCII inner box padding
  --list-themes               Print built-in theme names
  --help                      Show this help`)
}

function fail(message) {
  console.error(`beautiful-mermaid: ${message}`)
  process.exit(1)
}

function parseArgs(argv) {
  const opts = {
    format: 'svg',
    theme: 'github-light',
    colorMode: 'none',
    useAscii: false,
    transparent: false,
    interactive: false,
    listThemes: false,
  }

  const valueOptions = new Map([
    ['--format', 'format'],
    ['--input', 'input'],
    ['--output', 'output'],
    ['--theme', 'theme'],
    ['--bg', 'bg'],
    ['--fg', 'fg'],
    ['--line', 'line'],
    ['--accent', 'accent'],
    ['--muted', 'muted'],
    ['--surface', 'surface'],
    ['--border', 'border'],
    ['--font', 'font'],
    ['--padding', 'padding'],
    ['--node-spacing', 'nodeSpacing'],
    ['--layer-spacing', 'layerSpacing'],
    ['--component-spacing', 'componentSpacing'],
    ['--color-mode', 'colorMode'],
    ['--padding-x', 'paddingX'],
    ['--padding-y', 'paddingY'],
    ['--box-border-padding', 'boxBorderPadding'],
  ])

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === '--help' || arg === '-h') {
      opts.help = true
      continue
    }
    if (arg === '--list-themes') {
      opts.listThemes = true
      continue
    }
    if (arg === '--transparent') {
      opts.transparent = true
      continue
    }
    if (arg === '--interactive') {
      opts.interactive = true
      continue
    }
    if (arg === '--ascii') {
      opts.useAscii = true
      continue
    }
    if (!valueOptions.has(arg)) {
      fail(`unknown option: ${arg}`)
    }
    const key = valueOptions.get(arg)
    const value = argv[++i]
    if (value === undefined || value.startsWith('--')) {
      fail(`${arg} requires a value`)
    }
    opts[key] = value
  }

  if (!['svg', 'ascii'].includes(opts.format)) {
    fail('--format must be svg or ascii')
  }
  if (!['none', 'auto', 'ansi16', 'ansi256', 'truecolor', 'html'].includes(opts.colorMode)) {
    fail('--color-mode must be none, auto, ansi16, ansi256, truecolor, or html')
  }

  for (const key of ['padding', 'nodeSpacing', 'layerSpacing', 'componentSpacing', 'paddingX', 'paddingY', 'boxBorderPadding']) {
    if (opts[key] !== undefined) {
      const parsed = Number(opts[key])
      if (!Number.isFinite(parsed)) {
        fail(`--${key.replace(/[A-Z]/g, m => `-${m.toLowerCase()}`)} must be a number`)
      }
      opts[key] = parsed
    }
  }

  return opts
}

async function loadBeautifulMermaid() {
  if (process.env.BEAUTIFUL_MERMAID_BOOTSTRAPPED !== '1') {
    try {
      return await import('beautiful-mermaid')
    } catch {
      const result = spawnSync(
        'npm',
        ['exec', '--yes', `--package=${PACKAGE_SPEC}`, '--', process.execPath, SCRIPT_PATH, ...process.argv.slice(2)],
        {
          stdio: 'inherit',
          env: { ...process.env, BEAUTIFUL_MERMAID_BOOTSTRAPPED: '1' },
        },
      )
      process.exit(result.status ?? 1)
    }
  }

  try {
    return await import('beautiful-mermaid')
  } catch {
    const nodeModules = findNpmExecNodeModules()
    if (!nodeModules) {
      fail(`could not locate ${PACKAGE_SPEC}; run with Node/npm available from mise`)
    }
    return await import(pathToFileURL(path.join(nodeModules, 'beautiful-mermaid', 'dist', 'index.js')).href)
  }
}

function findNpmExecNodeModules() {
  const entries = (process.env.PATH ?? '').split(path.delimiter)
  const binDir = entries.find(entry =>
    entry.includes(`${path.sep}_npx${path.sep}`) &&
    entry.endsWith(`${path.sep}node_modules${path.sep}.bin`),
  )
  return binDir ? path.dirname(binDir) : null
}

async function readInput(opts) {
  if (opts.input) {
    return fs.readFileSync(opts.input, 'utf8')
  }
  return await new Promise((resolve, reject) => {
    let data = ''
    process.stdin.setEncoding('utf8')
    process.stdin.on('data', chunk => {
      data += chunk
    })
    process.stdin.on('end', () => resolve(data))
    process.stdin.on('error', reject)
  })
}

function writeOutput(opts, content) {
  if (!opts.output) {
    process.stdout.write(content)
    if (!content.endsWith('\n')) process.stdout.write('\n')
    return
  }
  const dir = path.dirname(opts.output)
  if (dir && dir !== '.') {
    fs.mkdirSync(dir, { recursive: true })
  }
  fs.writeFileSync(opts.output, content)
}

function supportedHeader(header) {
  return /^(?:graph|flowchart)\s+(?:TD|TB|LR|BT|RL)$/i.test(header) ||
    /^stateDiagram(?:-v2)?$/i.test(header) ||
    /^sequenceDiagram$/i.test(header) ||
    /^classDiagram$/i.test(header) ||
    /^erDiagram$/i.test(header) ||
    /^xychart(?:-beta)?(?:\s+horizontal)?$/i.test(header)
}

function normalizeMermaid(text) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const firstIndex = lines.findIndex(line => {
    const trimmed = line.trim()
    return trimmed.length > 0 && !trimmed.startsWith('%%')
  })
  if (firstIndex === -1) {
    fail('empty Mermaid input')
  }

  const first = lines[firstIndex].trim()
  if (first.includes(';')) {
    const pieces = first.split(';').map(piece => piece.trim()).filter(Boolean)
    if (pieces.length > 1 && supportedHeader(pieces[0])) {
      lines.splice(firstIndex, 1, pieces[0], ...pieces.slice(1))
    }
  }

  const normalizedFirst = lines[firstIndex].trim()
  if (!supportedHeader(normalizedFirst)) {
    fail(`unsupported Mermaid header "${normalizedFirst}". Supported: ${SUPPORTED.join(', ')}`)
  }

  return lines.join('\n')
}

function svgOptions(opts, themes) {
  const base = themes[opts.theme]
  if (!base) {
    fail(`unknown theme "${opts.theme}". Run --list-themes to inspect available themes`)
  }
  const result = { ...base }
  for (const key of ['bg', 'fg', 'line', 'accent', 'muted', 'surface', 'border', 'font', 'padding', 'nodeSpacing', 'layerSpacing', 'componentSpacing']) {
    if (opts[key] !== undefined) result[key] = opts[key]
  }
  if (opts.transparent) result.transparent = true
  if (opts.interactive) result.interactive = true
  return result
}

function asciiOptions(opts, themes) {
  const result = {
    useAscii: opts.useAscii,
    colorMode: opts.colorMode,
  }
  for (const key of ['paddingX', 'paddingY', 'boxBorderPadding']) {
    if (opts[key] !== undefined) result[key] = opts[key]
  }

  const theme = themes[opts.theme]
  const asciiTheme = {}
  const fg = opts.fg ?? theme?.fg
  const line = opts.line ?? theme?.line
  const border = opts.border ?? theme?.border
  const accent = opts.accent ?? theme?.accent
  if (fg) asciiTheme.fg = fg
  if (line) {
    asciiTheme.line = line
    asciiTheme.corner = line
  }
  if (border) {
    asciiTheme.border = border
    asciiTheme.junction = border
  }
  if (accent) asciiTheme.arrow = accent
  if (Object.keys(asciiTheme).length > 0) {
    result.theme = asciiTheme
  }
  return result
}

async function main() {
  const opts = parseArgs(process.argv.slice(2))
  if (opts.help) {
    printHelp()
    return
  }

  const mermaid = await loadBeautifulMermaid()
  const themes = mermaid.THEMES ?? {}

  if (opts.listThemes) {
    console.log(Object.keys(themes).sort().join('\n'))
    return
  }

  const source = normalizeMermaid(await readInput(opts))
  const output = opts.format === 'svg'
    ? mermaid.renderMermaidSVG(source, svgOptions(opts, themes))
    : mermaid.renderMermaidASCII(source, asciiOptions(opts, themes))
  writeOutput(opts, output)
}

main().catch(error => {
  fail(error instanceof Error ? error.message : String(error))
})
