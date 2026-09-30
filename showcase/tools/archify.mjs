#!/usr/bin/env node
/**
 * Build-time wrapper around the vendored Archify compiler.
 *
 * Archify stays a build-time tool: the interactive app never imports it and the
 * rendered artifacts land in `showcase/public/archify/`, where they are served
 * as static files and embedded as lazy-loaded iframes.
 *
 * Usage:
 *   node tools/archify.mjs validate-all [--quality standard|showcase]
 *   node tools/archify.mjs deliver-all  [--quality standard|showcase]
 *   node tools/archify.mjs validate <name>
 *   node tools/archify.mjs deliver  <name>
 *   node tools/archify.mjs list
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..");
const CLI = path.join(repoRoot, "vendor", "archify", "bin", "archify.mjs");
const IR_DIR = path.join(repoRoot, "archify");
const DIAGRAM_TYPES = new Set(["architecture", "sequence", "dataflow", "workflow", "lifecycle"]);
const IR_NAME = /^(?<name>[a-z0-9][a-z0-9-]*)\.(?<type>[a-z]+)\.json$/;

function fail(message) {
  console.error(`archify: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  const [command = "validate-all", ...rest] = argv;
  let quality = "showcase";
  const positional = [];
  for (let index = 0; index < rest.length; index += 1) {
    if (rest[index] === "--quality") {
      quality = rest[index + 1];
      index += 1;
    } else if (rest[index].startsWith("--quality=")) {
      quality = rest[index].split("=")[1];
    } else {
      positional.push(rest[index]);
    }
  }
  if (quality !== "standard" && quality !== "showcase") {
    fail(`unknown quality profile "${quality}" (expected standard or showcase)`);
  }
  return { command, quality, positional };
}

function discover() {
  if (!existsSync(IR_DIR)) fail(`no IR directory at ${IR_DIR}`);
  const artifacts = [];
  for (const entry of readdirSync(IR_DIR)) {
    const match = IR_NAME.exec(entry);
    if (!match || !DIAGRAM_TYPES.has(match.groups.type)) continue;
    const file = path.join(IR_DIR, entry);
    const ir = JSON.parse(readFileSync(file, "utf8"));
    if (ir.diagram_type !== match.groups.type) {
      fail(`${entry}: file name says "${match.groups.type}" but diagram_type is "${ir.diagram_type}"`);
    }
    const output = ir.meta?.output;
    if (!output) fail(`${entry}: meta.output is required so the app knows where to load the artifact`);
    const outputPath = path.isAbsolute(output) ? output : path.join(repoRoot, output);
    if (!outputPath.startsWith(path.join(repoRoot, "public"))) {
      fail(`${entry}: meta.output must live under public/ so Vite serves it as a static artifact`);
    }
    artifacts.push({ name: match.groups.name, type: match.groups.type, file, output, outputPath });
  }
  artifacts.sort((left, right) => left.name.localeCompare(right.name));
  if (artifacts.length === 0) fail(`no Archify IR files found in ${IR_DIR}`);
  return artifacts;
}

function runCli(args) {
  execFileSync(process.execPath, [CLI, ...args], { cwd: repoRoot, stdio: "inherit" });
}

function select(artifacts, positional) {
  const [name] = positional;
  if (!name) return artifacts;
  const wanted = artifacts.filter((artifact) => artifact.name === name);
  if (wanted.length === 0) fail(`no IR named "${name}"`);
  return wanted;
}

function validate(artifacts, quality) {
  const failures = [];
  for (const artifact of artifacts) {
    process.stdout.write(`validate  ${artifact.name} (${artifact.type})\n`);
    try {
      runCli(["validate", artifact.type, artifact.file, "--quality", quality, "--json"]);
    } catch {
      failures.push(artifact.name);
    }
  }
  return failures;
}

function deliver(artifacts, quality) {
  const failures = [];
  for (const artifact of artifacts) {
    process.stdout.write(`deliver   ${artifact.name} (${artifact.type})\n`);
    try {
      runCli(["deliver", artifact.type, artifact.file, artifact.outputPath, "--quality", quality]);
      if (!existsSync(artifact.outputPath) || statSync(artifact.outputPath).size === 0) {
        throw new Error(`expected artifact at ${artifact.output}`);
      }
      process.stdout.write(`          -> ${artifact.output}\n`);
    } catch (error) {
      console.error(`          !! ${error.message}`);
      failures.push(artifact.name);
    }
  }
  return failures;
}

const { command, quality, positional } = parseArgs(process.argv.slice(2));
const artifacts = discover();

switch (command) {
  case "list":
    for (const artifact of artifacts) {
      process.stdout.write(`${artifact.name}\t${artifact.type}\t${artifact.output}\n`);
    }
    break;
  case "validate":
  case "validate-all": {
    const failures = validate(select(artifacts, positional), quality);
    if (failures.length > 0) fail(`validation failed for: ${failures.join(", ")}`);
    process.stdout.write(`\nall ${artifacts.length} Archify artifacts validate at quality "${quality}".\n`);
    break;
  }
  case "deliver":
  case "deliver-all": {
    const chosen = select(artifacts, positional);
    const failures = deliver(chosen, quality);
    if (failures.length > 0) fail(`delivery failed for: ${failures.join(", ")}`);
    process.stdout.write(`\ndelivered ${chosen.length} Archify artifact(s) to public/archify/.\n`);
    break;
  }
  default:
    fail(`unknown command "${command}" (expected list, validate, validate-all, deliver or deliver-all)`);
}
