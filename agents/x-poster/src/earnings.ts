// Reads USDC Transfer events to the seller wallet on Base — the agent's
// ground-truth revenue feed. Public RPC, no API key needed.

import { createPublicClient, http, formatUnits, parseAbiItem } from "viem";
import { base } from "viem/chains";

const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
const TRANSFER = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");
const BLOCKS_PER_CHUNK = 10_000n; // public RPC getLogs range limit
const BASE_BLOCK_TIME_S = 2;

export interface EarningsReport {
  totalUsd: number;
  txCount: number;
  uniquePayers: number;
  txHashes: string[];
  sinceHours: number;
  balanceUsd: number;
}

export async function getEarnings(sellerAddress: `0x${string}`, sinceHours: number, rpcUrl?: string): Promise<EarningsReport> {
  const client = createPublicClient({ chain: base, transport: http(rpcUrl) });
  const latest = await client.getBlockNumber();
  const span = BigInt(Math.ceil((sinceHours * 3600) / BASE_BLOCK_TIME_S));
  const fromBlock = latest > span ? latest - span : 0n;

  const logs = [];
  for (let start = fromBlock; start <= latest; start += BLOCKS_PER_CHUNK) {
    const end = start + BLOCKS_PER_CHUNK - 1n > latest ? latest : start + BLOCKS_PER_CHUNK - 1n;
    logs.push(
      ...(await client.getLogs({
        address: USDC,
        event: TRANSFER,
        args: { to: sellerAddress },
        fromBlock: start,
        toBlock: end,
      }))
    );
  }

  const totalRaw = logs.reduce((s, l) => s + (l.args.value ?? 0n), 0n);
  const payers = new Set(logs.map((l) => l.args.from?.toLowerCase()));
  const balance = await client.readContract({
    address: USDC,
    abi: [{ name: "balanceOf", type: "function", stateMutability: "view", inputs: [{ type: "address" }], outputs: [{ type: "uint256" }] }] as const,
    functionName: "balanceOf",
    args: [sellerAddress],
  });

  return {
    totalUsd: Number(formatUnits(totalRaw, 6)),
    txCount: logs.length,
    uniquePayers: payers.size,
    txHashes: logs.map((l) => l.transactionHash),
    sinceHours,
    balanceUsd: Number(formatUnits(balance, 6)),
  };
}
