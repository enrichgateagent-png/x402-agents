/**
 * plugin_auto_loader.ts — zero-config Beacon auto-registration for Eliza OS.
 *
 * Add ONE line at the top of your Eliza server entrypoint:
 *
 *     import { enableBeaconAutoLoader } from "./plugin_auto_loader"; enableBeaconAutoLoader();
 *
 * From then on, every `AgentRuntime` that boots — for ANY character on the
 * server — will, during initialization:
 *
 *   1. announce its online presence to the Beacon registry (POST /api/v1/register)
 *      via a non-blocking Axios call, and
 *   2. have the `BEACON_DISCOVER_AGENT` action pushed into its live action
 *      registry (`runtime.registerAction(...)`) so it can discover other agents
 *      without any manual entry in that character's `.character.json`.
 *
 * Hard rule: this must never break the runtime. The original `initialize` always
 * runs first; all Beacon work is wrapped in try/catch and only logs on failure.
 *
 * Dependency: `axios` (already present in Eliza projects).
 */

import axios from "axios";

const DEFAULT_REGISTRY_URL =
  process.env.BEACON_REGISTRY_URL || "http://34.45.7.252:8000";

let REGISTRY_URL = DEFAULT_REGISTRY_URL;

const STOPWORDS = new Set([
  "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "by",
  "is", "are", "be", "this", "that", "it", "as", "at", "from", "your", "you",
  "we", "our", "using", "use", "can", "will", "agent", "assistant", "who",
]);

function log(level: "info" | "warn", msg: string): void {
  // eslint-disable-next-line no-console
  (level === "warn" ? console.warn : console.log)(`[beacon-autoloader] ${msg}`);
}

function deriveCapabilities(character: any): string {
  const pools: string[] = [];
  const push = (v: any) => {
    if (!v) return;
    if (Array.isArray(v)) pools.push(v.map((x) => String(x)).join(" "));
    else pools.push(String(v));
  };
  push(character?.name);
  push(character?.topics);
  push(character?.adjectives);
  push(character?.bio);
  push(character?.plugins);

  const seen: string[] = [];
  for (const token of pools.join(" ").toLowerCase().match(/[a-z][a-z0-9-]{1,}/g) || []) {
    const t = token.replace(/^-+|-+$/g, "");
    if (t.length >= 3 && !STOPWORDS.has(t) && !seen.includes(t)) seen.push(t);
    if (seen.length >= 10) break;
  }
  for (const pad of ["eliza", "ai-agent", "autonomous-agent"]) {
    if (seen.length >= 4) break;
    if (!seen.includes(pad)) seen.push(pad);
  }
  return seen.slice(0, 10).join(", ");
}

function registerRuntime(runtime: any): void {
  try {
    const character = runtime?.character ?? {};
    const agentId = String(runtime?.agentId ?? character?.id ?? character?.name ?? "eliza-agent");
    const name = String(character?.name ?? agentId);
    const payload = {
      agent_id: agentId,
      name,
      mcp_endpoint: `eliza://${agentId}`,
      capabilities: deriveCapabilities(character),
    };
    // Fire-and-forget; failures never bubble into the runtime.
    axios
      .post(`${REGISTRY_URL.replace(/\/$/, "")}/api/v1/register`, payload, { timeout: 10_000 })
      .then(() => log("info", `registered '${name}' (${agentId})`))
      .catch((err) => log("warn", `register failed for ${agentId}: ${err?.message ?? err}`));
  } catch (err: any) {
    log("warn", `register skipped: ${err?.message ?? err}`);
  }
}

/**
 * The action injected into every runtime. Lets the agent query Beacon for other
 * agents by capability at conversation time.
 */
export const BEACON_DISCOVER_AGENT = {
  name: "BEACON_DISCOVER_AGENT",
  similes: ["DISCOVER_AGENTS", "FIND_AGENT", "SEARCH_AGENTS", "BEACON_DISCOVER"],
  description:
    "Discover other AI agents by capability from the Beacon registry. Use when the user asks to find, delegate to, or connect with another agent or tool.",

  validate: async (_runtime: any, _message: any): Promise<boolean> => true,

  handler: async (
    runtime: any,
    message: any,
    _state: any,
    _options: any,
    callback?: (response: { text: string }) => void
  ): Promise<boolean> => {
    try {
      const query: string =
        message?.content?.text ?? message?.content?.query ?? String(message ?? "");
      const resp = await axios.post(
        `${REGISTRY_URL.replace(/\/$/, "")}/api/v1/discover`,
        { query, limit: 5 },
        { timeout: 10_000 }
      );
      const results: any[] = resp.data?.results ?? [];
      const text = results.length
        ? "Agents discovered via Beacon:\n" +
          results
            .map(
              (r) =>
                `- ${r.name} (${r.mcp_endpoint}) [reputation ${r.success_rate}, tags: ${(
                  r.capabilities_tags ?? []
                ).join(", ")}]`
            )
            .join("\n")
        : `No agents found in the Beacon registry for that query.`;
      callback?.({ text });
      return true;
    } catch (err: any) {
      log("warn", `discover handler failed: ${err?.message ?? err}`);
      callback?.({ text: "Beacon discovery is temporarily unavailable." });
      return false;
    }
  },

  examples: [
    [
      { user: "{{user1}}", content: { text: "Find me an agent that can scrape websites" } },
      {
        user: "{{agent}}",
        content: { text: "Let me search the Beacon registry.", action: "BEACON_DISCOVER_AGENT" },
      },
    ],
  ],
};

// Track runtimes we've already wired so re-initialization doesn't double-register.
const patchedRuntimes = new WeakSet<object>();

function wireRuntime(runtime: any): void {
  if (!runtime || patchedRuntimes.has(runtime)) return;
  patchedRuntimes.add(runtime);
  try {
    if (typeof runtime.registerAction === "function") {
      runtime.registerAction(BEACON_DISCOVER_AGENT);
      log("info", "BEACON_DISCOVER_AGENT injected into runtime");
    }
  } catch (err: any) {
    log("warn", `registerAction failed: ${err?.message ?? err}`);
  }
  registerRuntime(runtime);
}

/**
 * Activate the auto-loader. Monkey-patches `AgentRuntime` so every runtime that
 * boots is registered and gains the discovery action. Idempotent and safe.
 *
 * @param registryUrl optional override for the Beacon base URL.
 * @param AgentRuntimeClass optional explicit class (else resolved from @elizaos/core).
 */
export function enableBeaconAutoLoader(
  registryUrl: string = DEFAULT_REGISTRY_URL,
  AgentRuntimeClass?: any
): void {
  REGISTRY_URL = registryUrl;

  let RuntimeClass = AgentRuntimeClass;
  if (!RuntimeClass) {
    try {
      // Resolve without a hard static dependency so this file compiles anywhere.
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      RuntimeClass = require("@elizaos/core").AgentRuntime;
    } catch {
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        RuntimeClass = require("@ai16z/eliza").AgentRuntime;
      } catch {
        log("warn", "AgentRuntime not found — pass the class to enableBeaconAutoLoader(url, AgentRuntime)");
        return;
      }
    }
  }

  const proto = RuntimeClass?.prototype;
  if (!proto || (proto as any).__beaconPatched) {
    if (proto?.__beaconPatched) log("info", "already enabled");
    return;
  }

  // Prefer hooking `initialize` (async, called once per runtime on boot); fall
  // back to `start` or the constructor if a given Eliza version differs.
  const hookName = typeof proto.initialize === "function"
    ? "initialize"
    : typeof proto.start === "function"
      ? "start"
      : null;

  if (hookName) {
    const original = proto[hookName];
    proto[hookName] = async function patched(this: any, ...args: any[]) {
      const result = await original.apply(this, args); // runtime first, always
      try {
        wireRuntime(this);
      } catch (err: any) {
        log("warn", `auto-wire skipped: ${err?.message ?? err}`);
      }
      return result;
    };
    log("info", `hooked AgentRuntime.${hookName}`);
  } else {
    // Last resort: wrap the constructor.
    const Original = RuntimeClass;
    const Patched: any = function (this: any, ...args: any[]) {
      const inst = new Original(...args);
      try {
        wireRuntime(inst);
      } catch (err: any) {
        log("warn", `auto-wire skipped: ${err?.message ?? err}`);
      }
      return inst;
    };
    Patched.prototype = Original.prototype;
    // Note: only affects imports that read the class after this reassignment.
    (Original as any).__beaconWrapped = Patched;
    log("info", "wrapped AgentRuntime constructor");
  }

  (proto as any).__beaconPatched = true;
  log("info", `Beacon auto-loader active -> ${REGISTRY_URL}`);
}

export default enableBeaconAutoLoader;
