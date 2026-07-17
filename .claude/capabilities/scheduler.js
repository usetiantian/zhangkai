#!/usr/bin/env node
/**
 * CC Scheduler — Background task manager
 *
 * Manages long-running tasks: start, check status, list, kill.
 * Tasks run in background and write status to a JSON log.
 *
 * Usage:
 *   node scheduler.js start  <name> <command...>
 *   node scheduler.js status <name>
 *   node scheduler.js list
 *   node scheduler.js kill   <name>
 *   node scheduler.js tail   <name> [lines]
 */

import { spawn } from "child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync, appendFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TASKS_DIR = resolve(__dirname, "../../.tasks");
const TASKS_FILE = resolve(TASKS_DIR, "tasks.json");
const LOGS_DIR = resolve(TASKS_DIR, "logs");

if (!existsSync(TASKS_DIR)) mkdirSync(TASKS_DIR, { recursive: true });
if (!existsSync(LOGS_DIR)) mkdirSync(LOGS_DIR, { recursive: true });

function loadTasks() {
  if (!existsSync(TASKS_FILE)) return {};
  return JSON.parse(readFileSync(TASKS_FILE, "utf-8"));
}

function saveTasks(tasks) {
  writeFileSync(TASKS_FILE, JSON.stringify(tasks, null, 2));
}

async function start(name, command, args) {
  const tasks = loadTasks();
  if (tasks[name] && tasks[name].status === "running") {
    console.log(JSON.stringify({ error: `Task '${name}' is already running`, pid: tasks[name].pid }));
    return;
  }

  const logFile = resolve(LOGS_DIR, `${name}.log`);
  const logStream = require("fs").createWriteStream(logFile, { flags: "a" });

  const child = spawn(command, args, {
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    shell: true,
  });

  const task = {
    name,
    command: `${command} ${args.join(" ")}`,
    pid: child.pid,
    started: new Date().toISOString(),
    status: "running",
    logFile,
  };

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

  child.on("exit", (code) => {
    const tasks = loadTasks();
    if (tasks[name]) {
      tasks[name].status = code === 0 ? "completed" : "failed";
      tasks[name].exitCode = code;
      tasks[name].ended = new Date().toISOString();
      saveTasks(tasks);
      appendFileSync(logFile, `\n[CC Scheduler] Task '${name}' exited with code ${code} at ${new Date().toISOString()}\n`);
    }
  });

  tasks[name] = task;
  saveTasks(tasks);

  console.log(JSON.stringify({ started: task }));
}

function status(name) {
  const tasks = loadTasks();
  if (!tasks[name]) {
    console.log(JSON.stringify({ error: `No task named '${name}'` }));
    return;
  }
  console.log(JSON.stringify(tasks[name]));
}

function list() {
  const tasks = loadTasks();
  const entries = Object.entries(tasks).map(([name, t]) => ({
    name,
    status: t.status,
    pid: t.pid,
    started: t.started,
    command: t.command,
  }));
  console.log(JSON.stringify(entries));
}

function kill(name) {
  const tasks = loadTasks();
  if (!tasks[name]) {
    console.log(JSON.stringify({ error: `No task named '${name}'` }));
    return;
  }
  try {
    process.kill(tasks[name].pid, "SIGTERM");
    tasks[name].status = "killed";
    tasks[name].ended = new Date().toISOString();
    saveTasks(tasks);
    console.log(JSON.stringify({ killed: tasks[name] }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
  }
}

function tail(name, lines = 20) {
  const tasks = loadTasks();
  if (!tasks[name]) {
    console.log(JSON.stringify({ error: `No task named '${name}'` }));
    return;
  }
  const logFile = tasks[name].logFile;
  if (!existsSync(logFile)) {
    console.log(JSON.stringify({ error: `Log file not found: ${logFile}` }));
    return;
  }
  const content = readFileSync(logFile, "utf-8");
  const allLines = content.split("\n").filter(Boolean);
  console.log(allLines.slice(-lines).join("\n"));
}

// ── CLI ──────────────────────────────────────────────────────────────
const [action, taskName, ...rest] = process.argv.slice(2);

switch (action) {
  case "start":
    if (!taskName || rest.length === 0) {
      console.log(JSON.stringify({ error: "Usage: scheduler.js start <name> <command...>" }));
      process.exit(1);
    }
    await start(taskName, rest[0], rest.slice(1));
    break;
  case "status":
    if (!taskName) {
      console.log(JSON.stringify({ error: "Usage: scheduler.js status <name>" }));
      process.exit(1);
    }
    status(taskName);
    break;
  case "list":
    list();
    break;
  case "kill":
    if (!taskName) {
      console.log(JSON.stringify({ error: "Usage: scheduler.js kill <name>" }));
      process.exit(1);
    }
    kill(taskName);
    break;
  case "tail":
    tail(taskName, parseInt(rest[0]) || 20);
    break;
  default:
    console.log(JSON.stringify({
      error: "Unknown action",
      usage: {
        "start <name> <cmd...>": "Start a background task",
        "status <name>": "Check task status",
        "list": "List all tasks",
        "kill <name>": "Kill a running task",
        "tail <name> [lines]": "View task log",
      },
    }));
}
