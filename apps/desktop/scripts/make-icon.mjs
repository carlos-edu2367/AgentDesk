import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import sharp from 'sharp'
import pngToIco from 'png-to-ico'

const here = dirname(fileURLToPath(import.meta.url))
const buildDir = join(here, '..', 'build')
const svg = readFileSync(join(buildDir, 'icon.svg'))

const sizes = [16, 24, 32, 48, 64, 128, 256]
const pngs = await Promise.all(
  sizes.map(s => sharp(svg, { density: 384 }).resize(s, s).png().toBuffer()),
)
const ico = await pngToIco(pngs)
writeFileSync(join(buildDir, 'icon.ico'), ico)
writeFileSync(join(buildDir, 'icon.png'), pngs[pngs.length - 1])
console.log('Wrote build/icon.ico and build/icon.png')
