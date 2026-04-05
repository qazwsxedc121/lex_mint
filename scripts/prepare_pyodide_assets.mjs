import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend');
const pyodideSourceDir = path.join(frontendRoot, 'node_modules', 'pyodide');
const pyodideTargetDir = path.join(frontendRoot, 'public', 'pyodide');

const requiredFiles = [
  'pyodide.mjs',
  'pyodide.asm.js',
  'pyodide.asm.wasm',
  'pyodide-lock.json',
  'python_stdlib.zip',
];

function assertSourceExists() {
  if (!fs.existsSync(pyodideSourceDir)) {
    throw new Error(
      `Pyodide package not found at ${pyodideSourceDir}. Run 'npm install' in frontend first.`,
    );
  }
}

function cleanTarget() {
  fs.rmSync(pyodideTargetDir, { recursive: true, force: true });
  fs.mkdirSync(pyodideTargetDir, { recursive: true });
}

function copyRequiredFiles() {
  for (const fileName of requiredFiles) {
    const sourcePath = path.join(pyodideSourceDir, fileName);
    const targetPath = path.join(pyodideTargetDir, fileName);

    if (!fs.existsSync(sourcePath)) {
      throw new Error(`Required pyodide runtime file is missing: ${sourcePath}`);
    }

    fs.copyFileSync(sourcePath, targetPath);
  }
}

function main() {
  assertSourceExists();
  cleanTarget();
  copyRequiredFiles();
  console.log(`[pyodide] prepared local runtime assets in ${pyodideTargetDir}`);
}

main();
