import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const schemaScript = path.join(repoRoot, "scripts", "generate_workflow_schema.py");
const passthroughArgs = process.argv.slice(2);

const pythonCandidates = [
  path.join(repoRoot, "venv", "Scripts", "python.exe"),
  path.join(repoRoot, "venv", "bin", "python"),
];

const pythonExecutable = pythonCandidates.find((candidate) => existsSync(candidate));

if (!pythonExecutable) {
  console.error("[schema] Could not find a venv python executable.");
  console.error(`[schema] Expected one of: ${pythonCandidates.join(", ")}`);
  process.exit(1);
}

const result = spawnSync(pythonExecutable, [schemaScript, ...passthroughArgs], {
  stdio: "inherit",
  cwd: repoRoot,
});

if (result.error) {
  console.error(`[schema] Failed to run schema generator: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
