import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const DEFAULT_VVV_KEYCHAIN_SERVICE = "vertu-vvv-user-robot";

type Attachment = {
  attachment_type: "image";
  name: string;
  mime_type: string;
  url: string;
};

export type VvvConfig = {
  appId: string;
  appSecret: string;
  channelId: string;
  endpoint: string;
  timeoutMs: number;
};

export type VvvReceipt = {
  provider: "vvv_user_robot";
  status: "PREVIEW" | "SENT" | "FAILED" | "DELIVERY_UNKNOWN";
  app_id: string;
  channel_id: string;
  endpoint: string;
  http_status: number | null;
  event_id: string | null;
  message_id: string | null;
  delivered_at: string | null;
  attempted_at: string;
  body_sha256: string;
  body_length: number;
  attachment_count: number;
  error: string | null;
};

type PushOptions = {
  body: string;
  attachments?: Attachment[];
  config: VvvConfig;
  fetchImpl?: typeof fetch;
};

function readPositiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0
    ? Math.floor(parsed)
    : fallback;
}

function readKeychainSecret(appId: string) {
  if (process.platform !== "darwin") return null;
  try {
    const value = execFileSync(
      "security",
      [
        "find-generic-password",
        "-s",
        process.env.VERTU_VVV_KEYCHAIN_SERVICE ??
          DEFAULT_VVV_KEYCHAIN_SERVICE,
        "-a",
        appId,
        "-w",
      ],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
    return value || null;
  } catch {
    return null;
  }
}

export function resolveVvvConfig(
  env: Record<string, string | undefined> = process.env,
): VvvConfig {
  const appId = env.VERTU_VVV_APP_ID ?? "";
  const appSecret =
    env.VERTU_VVV_APP_SECRET ?? readKeychainSecret(appId) ?? "";
  const channelId = env.VERTU_VVV_CHANNEL_ID ?? "";
  const endpoint = env.VERTU_VVV_PUSH_ENDPOINT ?? "";

  if (!appId) {
    throw new Error("VVV_CONFIG_MISSING_APP_ID");
  }
  if (!appId.startsWith("vbot_")) {
    throw new Error("VVV_CONFIG_INVALID_APP_ID");
  }
  if (!channelId) {
    throw new Error("VVV_CONFIG_MISSING_CHANNEL_ID");
  }
  if (!/^[0-9a-f-]{36}$/i.test(channelId)) {
    throw new Error("VVV_CONFIG_INVALID_CHANNEL_ID");
  }
  if (!endpoint) {
    throw new Error("VVV_CONFIG_MISSING_ENDPOINT");
  }
  const parsedEndpoint = new URL(endpoint);
  if (parsedEndpoint.protocol !== "https:") {
    throw new Error("VVV_CONFIG_INVALID_ENDPOINT");
  }

  return {
    appId,
    appSecret,
    channelId,
    endpoint,
    timeoutMs: readPositiveInteger(env.VERTU_VVV_TIMEOUT_MS, 15_000),
  };
}

function baseReceipt(
  config: VvvConfig,
  body: string,
  attachments: Attachment[],
): VvvReceipt {
  return {
    provider: "vvv_user_robot",
    status: "PREVIEW",
    app_id: config.appId,
    channel_id: config.channelId,
    endpoint: config.endpoint,
    http_status: null,
    event_id: null,
    message_id: null,
    delivered_at: null,
    attempted_at: new Date().toISOString(),
    body_sha256: createHash("sha256").update(body).digest("hex"),
    body_length: body.length,
    attachment_count: attachments.length,
    error: null,
  };
}

export async function pushVvvMessage({
  body,
  attachments = [],
  config,
  fetchImpl = fetch,
}: PushOptions): Promise<VvvReceipt> {
  const receipt = baseReceipt(config, body, attachments);
  if (!body.trim()) {
    return { ...receipt, status: "FAILED", error: "VVV_EMPTY_BODY" };
  }
  if (!config.appSecret) {
    return {
      ...receipt,
      status: "FAILED",
      error: "VVV_APP_SECRET_UNAVAILABLE",
    };
  }

  try {
    const response = await fetchImpl(config.endpoint, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-vertu-bot-app-id": config.appId,
        "x-vertu-bot-app-secret": config.appSecret,
      },
      body: JSON.stringify({
        channel_id: config.channelId,
        body,
        ...(attachments.length ? { attachments } : {}),
      }),
      signal: AbortSignal.timeout(config.timeoutMs),
    });
    const payload = (await response.json().catch(() => null)) as {
      ok?: boolean;
      event_id?: string;
      message?: {
        id?: string;
        delivered_at?: string;
      };
      error?: string;
    } | null;
    const sent = response.ok && payload?.ok === true;
    return {
      ...receipt,
      status: sent ? "SENT" : "FAILED",
      http_status: response.status,
      event_id: payload?.event_id ?? null,
      message_id: payload?.message?.id ?? null,
      delivered_at: payload?.message?.delivered_at ?? null,
      error: sent
        ? null
        : payload?.error?.slice(0, 300) ?? `VVV_HTTP_${response.status}`,
    };
  } catch (error) {
    return {
      ...receipt,
      status: "DELIVERY_UNKNOWN",
      error:
        error instanceof Error
          ? `VVV_TRANSPORT_ERROR:${error.name}`
          : "VVV_TRANSPORT_ERROR",
    };
  }
}

function readOption(args: string[], name: string) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
}

function writeReceipt(filePath: string | undefined, receipt: VvvReceipt) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(
    path.resolve(filePath),
    `${JSON.stringify(receipt, null, 2)}\n`,
    { mode: 0o600 },
  );
}

export async function runCli(args = process.argv.slice(2)) {
  const bodyFile = readOption(args, "--body-file");
  const receiptFile = readOption(args, "--receipt-file");
  const attachmentsFile = readOption(args, "--attachments-file");
  const send = args.includes("--send");
  const preview = args.includes("--preview");
  if ((!send && !preview) || !bodyFile) {
    throw new Error(
      "Usage: --send|--preview --body-file <path> [--attachments-file <path>] [--receipt-file <path>]",
    );
  }

  const body = fs.readFileSync(path.resolve(bodyFile), "utf8").trim();
  const attachments = attachmentsFile
    ? (JSON.parse(
        fs.readFileSync(path.resolve(attachmentsFile), "utf8"),
      ) as Attachment[])
    : [];
  const config = resolveVvvConfig();
  const receipt = send
    ? await pushVvvMessage({ body, attachments, config })
    : baseReceipt(config, body, attachments);
  writeReceipt(receiptFile, receipt);
  console.log(JSON.stringify(receipt, null, 2));
  if (send && receipt.status !== "SENT") process.exitCode = 1;
  return receipt;
}

const isMain =
  Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain) {
  runCli().catch((error) => {
    console.error(
      error instanceof Error ? error.message : "VVV_NOTIFY_FAILED",
    );
    process.exitCode = 1;
  });
}
