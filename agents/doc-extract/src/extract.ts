// Document → structured JSON pipeline:
// 1. fetch the document (PDF, image, DOCX, HTML …)
// 2. Cloudflare Workers AI toMarkdown converts it to text
// 3. an LLM structures the text into the requested JSON fields

const CF_ACCOUNT = () => process.env.CF_ACCOUNT_ID!;
const CF_TOKEN = () => process.env.CF_API_TOKEN!;
const MAX_BYTES = 10 * 1024 * 1024;

const DEFAULT_FIELDS =
  "doc_type (invoice/receipt/contract/report/letter/other), issuer, recipient, date, currency, total_amount, line_items (array of {description, qty, amount}), key_facts (array of strings)";

export interface Extraction {
  url: string;
  fields: Record<string, unknown> | null;
  markdown: string;
  model: string;
  warning?: string;
}

export async function extractDocument(url: string, fieldSpec?: string): Promise<Extraction> {
  // 1. fetch document
  const doc = await fetch(url, { signal: AbortSignal.timeout(20000), redirect: "follow" });
  if (!doc.ok) throw new Error(`Could not fetch document (${doc.status})`);
  const buf = Buffer.from(await doc.arrayBuffer());
  if (buf.byteLength > MAX_BYTES) throw new Error("Document exceeds 10MB limit");
  const name = new URL(url).pathname.split("/").pop() || "document";

  // 2. convert to markdown
  const form = new FormData();
  form.append("files", new Blob([buf], { type: doc.headers.get("content-type") ?? "application/octet-stream" }), name);
  const mdRes = await fetch(`https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT()}/ai/tomarkdown`, {
    method: "POST",
    headers: { authorization: `Bearer ${CF_TOKEN()}` },
    body: form,
    signal: AbortSignal.timeout(45000),
  });
  const md: any = await mdRes.json();
  if (!md.success || !md.result?.[0]?.data) {
    throw new Error(`Conversion failed: ${md.errors?.[0]?.message ?? "unsupported format"}`);
  }
  const markdown: string = md.result.map((r: any) => r.data).join("\n\n");

  // 3. structure with LLM
  const model = process.env.CF_AI_MODEL ?? "@cf/meta/llama-3.1-8b-instruct-fp8";
  const llmRes = await fetch(`https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT()}/ai/run/${model}`, {
    method: "POST",
    headers: { authorization: `Bearer ${CF_TOKEN()}`, "content-type": "application/json" },
    body: JSON.stringify({
      messages: [
        {
          role: "system",
          content: `Extract the requested fields from the document text. Respond with ONLY a valid JSON object, no prose, no markdown fences. Use null for fields not present. Fields: ${fieldSpec ?? DEFAULT_FIELDS}`,
        },
        { role: "user", content: markdown.slice(0, 12000) },
      ],
    }),
    signal: AbortSignal.timeout(45000),
  });
  const llm: any = await llmRes.json();
  const raw: string = llm.result?.response ?? "";

  let fields: Record<string, unknown> | null = null;
  let warning: string | undefined;
  try {
    const jsonText = raw.replace(/^```(json)?\s*/i, "").replace(/\s*```$/, "");
    fields = JSON.parse(jsonText.slice(jsonText.indexOf("{"), jsonText.lastIndexOf("}") + 1));
  } catch {
    warning = "LLM output was not clean JSON — see markdown and raw fields";
    fields = { raw };
  }

  return { url, fields, markdown: markdown.slice(0, 20000), model, warning };
}
