import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend');
const pyodideSourceDir = path.join(frontendRoot, 'node_modules', 'pyodide');
const pyodideTargetDir = path.join(frontendRoot, 'public', 'pyodide');
const pyodideLockFileName = 'pyodide-lock.json';
const shouldSyncLock = process.argv.includes('--sync-lock');

const requiredFiles = [
  'pyodide.mjs',
  'pyodide.asm.js',
  'pyodide.asm.wasm',
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

function syncOrPreservePyodideLock(previousLockBuffer) {
  const targetPath = path.join(pyodideTargetDir, pyodideLockFileName);
  const sourcePath = path.join(pyodideSourceDir, pyodideLockFileName);
  if (!fs.existsSync(sourcePath)) {
    throw new Error(`Required pyodide runtime file is missing: ${sourcePath}`);
  }

  const sourceLockBuffer = fs.readFileSync(sourcePath);

  if (shouldSyncLock) {
    fs.writeFileSync(targetPath, sourceLockBuffer);
    return 'synced';
  }

  if (previousLockBuffer) {
    const hasDiff = !previousLockBuffer.equals(sourceLockBuffer);
    fs.writeFileSync(targetPath, previousLockBuffer);
    return hasDiff ? 'preserved_with_diff' : 'preserved';
  }

  fs.writeFileSync(targetPath, sourceLockBuffer);
  return 'copied';
}

function main() {
  assertSourceExists();
  const existingLockPath = path.join(pyodideTargetDir, pyodideLockFileName);
  const previousLockBuffer = fs.existsSync(existingLockPath)
    ? fs.readFileSync(existingLockPath)
    : null;
  cleanTarget();
  copyRequiredFiles();
  const lockAction = syncOrPreservePyodideLock(previousLockBuffer);
  console.log(`[pyodide] prepared local runtime assets in ${pyodideTargetDir}`);
  if (lockAction === 'synced') {
    console.log(`[pyodide] synced ${pyodideLockFileName} from node_modules (--sync-lock)`);
    return;
  }
  if (lockAction === 'preserved_with_diff') {
    console.log(`[pyodide] preserved ${pyodideLockFileName} (local differs from node_modules)`);
    console.log(`[pyodide] run "npm run prepare:pyodide:sync-lock" if you intentionally want to update it`);
    return;
  }
  console.log(`[pyodide] ${lockAction === 'preserved' ? 'preserved' : 'copied'} ${pyodideLockFileName}`);
}

main();
