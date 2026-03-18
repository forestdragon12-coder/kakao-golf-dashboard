const functions = require("firebase-functions/v1");
const admin = require("firebase-admin");
const OpenAI = require("openai");

admin.initializeApp();
const db = admin.firestore();

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return [];

  return messages
    .filter((message) => message && typeof message.content === "string")
    .map((message) => ({
      role: ["user", "assistant", "system", "developer"].includes(message.role) ?
        message.role :
        "user",
      content: message.content.trim(),
    }))
    .filter((message) => message.content);
}

let openaiClient = null;

exports.aiChat = functions
  .region("us-central1")
  .runWith({ secrets: ["OPENAI_API_KEY"], maxInstances: 5, memory: "512MB", timeoutSeconds: 300 })
  .https.onRequest(async (req, res) => {
    const isLocalEmulator = process.env.FUNCTIONS_EMULATOR === "true";
    const localAdminEmail = String(req.headers["x-local-admin-email"] || "").trim();
    const useLocalMock = isLocalEmulator && String(req.headers["x-local-mock-response"] || "") === "1";

    // CORS
    res.set("Access-Control-Allow-Origin", "*");
    res.set("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Local-Admin-Email, X-Local-Mock-Response");
    if (req.method === "OPTIONS") { res.status(204).send(""); return; }

    if (req.method !== "POST") {
      res.status(405).send("Method Not Allowed");
      return;
    }

    let email = "";

    if (isLocalEmulator && localAdminEmail) {
      email = localAdminEmail;
      functions.logger.info("aiChat local emulator bypass", { email });
    } else {
      // 인증 검증
      const authHeader = req.headers.authorization || "";
      const idToken = authHeader.replace("Bearer ", "");
      if (!idToken) {
        res.status(401).json({ error: "인증 토큰 없음" });
        return;
      }

      try {
        const decoded = await admin.auth().verifyIdToken(idToken);
        email = decoded.email || "";
      } catch (e) {
        res.status(401).json({ error: "토큰 검증 실패" });
        return;
      }

      // admin 권한 확인
      if (!email) {
        res.status(403).json({ error: "이메일 계정만 사용할 수 있습니다" });
        return;
      }

      try {
        const userDoc = await db.collection("approved_users").doc(email).get();
        if (!userDoc.exists || userDoc.data().role !== "admin") {
          res.status(403).json({ error: "관리자 권한 필요" });
          return;
        }
      } catch (e) {
        res.status(403).json({ error: "권한 확인 실패" });
        return;
      }
    }

    // OpenAI API 키
    const apiKey = (process.env.OPENAI_API_KEY || "").trim();
    if (!apiKey && !useLocalMock) {
      res.status(500).json({ error: "API 키 미설정" });
      return;
    }

    const { system, messages, model, reasoning_effort, stream: wantStream } = req.body;
    if (!Array.isArray(messages)) {
      res.status(400).json({ error: "messages 배열 필요" });
      return;
    }

    const ALLOWED_MODELS = ["gpt-5.4", "gpt-5", "gpt-5-mini"];
    const selectedModel = ALLOWED_MODELS.includes(model) ? model : "gpt-5.4";
    const ALLOWED_EFFORTS = ["none", "low", "medium", "high", "xhigh"];
    const selectedEffort = ALLOWED_EFFORTS.includes(reasoning_effort) && reasoning_effort !== "none" ? reasoning_effort : undefined;
    const input = normalizeMessages(messages)
      .map((m) => ({ ...m, content: m.content.slice(0, 2000) }))
      .slice(-10);

    if (input.length === 0) {
      res.status(400).json({ error: "대화 내용이 비어 있습니다" });
      return;
    }

    if (useLocalMock) {
      const lastUserMessage = [...input].reverse().find((message) => message.role === "user");
      const prompt = lastUserMessage?.content || "질문 없음";
      res.json({
        reply: `[local mock] "${prompt}"에 대한 테스트 응답입니다. 현재 localhost에서 aiChat 왕복이 정상 동작합니다.`,
        usage: {
          input_tokens: Math.max(prompt.length, 1),
          output_tokens: 24,
          total_tokens: Math.max(prompt.length, 1) + 24,
          model: `${selectedModel}-mock`,
        },
      });
      return;
    }

    try {
      if (!openaiClient || openaiClient._apiKey !== apiKey) {
        openaiClient = new OpenAI({ apiKey });
        openaiClient._apiKey = apiKey;
      }
      const client = openaiClient;
      const reqBody = {
        model: selectedModel,
        instructions: system || "골프장 운영 분석 전문가입니다.",
        max_output_tokens: 1024,
        input,
      };
      if (selectedEffort) reqBody.reasoning = { effort: selectedEffort };

      if (wantStream) {
        // 스트리밍 응답
        res.set("Content-Type", "text/event-stream");
        res.set("Cache-Control", "no-cache");
        res.set("Connection", "keep-alive");
        reqBody.stream = true;
        const stream = await client.responses.create(reqBody);
        let fullText = "";
        let usage = {};
        for await (const event of stream) {
          if (event.type === "response.output_text.delta") {
            fullText += event.delta;
            res.write(`data: ${JSON.stringify({ type: "delta", delta: event.delta })}\n\n`);
          } else if (event.type === "response.completed") {
            usage = event.response?.usage || {};
          }
        }
        res.write(`data: ${JSON.stringify({ type: "done", usage: { input_tokens: usage.input_tokens || 0, output_tokens: usage.output_tokens || 0, total_tokens: usage.total_tokens || 0, model: selectedModel } })}\n\n`);
        res.end();
        return;
      }

      // 일반 응답
      const response = await client.responses.create(reqBody);
      const reply = response.output_text || "";
      const usage = response.usage || {};
      res.json({
        reply,
        usage: {
          input_tokens: usage.input_tokens || 0,
          output_tokens: usage.output_tokens || 0,
          total_tokens: usage.total_tokens || 0,
          model: selectedModel,
        },
      });
    } catch (e) {
      functions.logger.error("aiChat OpenAI error", {
        status: e?.status,
        message: e?.message,
        code: e?.code,
        type: e?.type,
        cause: (e?.cause?.message || e?.cause?.code || String(e?.cause || "")).replace(/sk-[A-Za-z0-9_-]+/g, "sk-***"),
        email,
        model: selectedModel,
      });
      const statusCode = typeof e?.status === "number" ? e.status : 500;
      res.status(statusCode).json({ error: `OpenAI API 오류: ${e.message}` });
    }
  });
