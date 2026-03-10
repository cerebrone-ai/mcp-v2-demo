// simple_mcp_client.js
// A lightweight vanilla JS implementation of the protocol for the demo

export class SimpleMCPClient {
    constructor(serverUrl, token) {
        this.serverUrl = serverUrl;
        this.token = token;
        this.messageId = 1;
        this.resolvers = {};
        this.postEndpoint = null;
        this.onLog = (msg) => console.log(msg);

        // This simulates a local "Model" solving the sample request
        this.localLLM = (prompt) => {
            return `[Client-side Simulation] I have analyzed the text. It contains key entities but requires further structuring.`;
        };
    }

    async connect() {
        return new Promise((resolve, reject) => {
            this.onLog(`[Auth] Connecting to ${this.serverUrl}/sse with token...`);

            // Connect to SSE using token query param
            this.es = new EventSource(`${this.serverUrl}/sse?token=${this.token}`);

            this.es.onmessage = (e) => {
                const data = JSON.parse(e.data);

                // Handle JSON-RPC Responses
                if (data.id && this.resolvers[data.id]) {
                    this.resolvers[data.id](data);
                    delete this.resolvers[data.id];
                }
                // Handle JSON-RPC Requests from Server (e.g. Sampling)
                else if (data.method) {
                    this.handleServerRequest(data);
                }
            };

            this.es.addEventListener('endpoint', async (e) => {
                this.postEndpoint = new URL(e.data, `${this.serverUrl}/sse`).toString();
                this.onLog(`[Transport] SSE established. POST endpoint: ${this.postEndpoint}`);
                try {
                    await this.initializeSession();
                    resolve();
                } catch (err) {
                    reject(err);
                }
            });

            this.es.onerror = (err) => {
                this.onLog(`[Error] SSE connection failed.`);
                reject(new Error("SSE Error"));
            };
        });
    }

    async send(method, params = {}) {
        const id = this.messageId++;
        const payload = { jsonrpc: "2.0", id, method, params };

        const res = await fetch(this.postEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        return new Promise((resolve) => {
            // Store resolver to be called when SSE message arrives
            this.resolvers[id] = resolve;
        });
    }

    async respondToServer(id, result) {
        const payload = { jsonrpc: "2.0", id, result };
        await fetch(this.postEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    async handleServerRequest(req) {
        this.onLog(`[Sampling] Server requested ${req.method} (id: ${req.id})`);

        if (req.method === "sampling/createMessage") {
            const messages = req.params.messages;
            const prompt = messages[0].content.text;
            this.onLog(`[Sampling] Server asked local LLM: "${prompt}"`);

            // Simulate client LLM execution
            setTimeout(async () => {
                const answer = this.localLLM(prompt);
                this.onLog(`[Sampling] Providing local answer back to server...`);

                await this.respondToServer(req.id, {
                    role: "assistant",
                    content: { type: "text", text: answer },
                    model: "local-demo-model",
                    stopReason: "endTurn"
                });
            }, 1000);
        }
    }

    async initializeSession() {
        this.onLog("[Protocol] Sending initialize request...");
        const initRes = await this.send("initialize", {
            protocolVersion: "2024-11-05", // Spec version
            capabilities: {
                sampling: {} // We announce we support sampling
            },
            clientInfo: {
                name: "VanillaBrowserDemo",
                version: "1.0.0"
            }
        });

        if (initRes.error) throw new Error(initRes.error.message);

        // Send initialized notification
        await fetch(this.postEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" })
        });

        this.onLog("[Protocol] Session perfectly initialized! Agent Contracts active.");
    }

    async listTools() {
        const res = await this.send("tools/list");
        return res.result.tools;
    }

    async callTool(name, args) {
        this.onLog(`[Execution] Calling tool '${name}'...`);
        const res = await this.send("tools/call", {
            name: name,
            arguments: args
        });
        if (res.error) throw new Error(res.error.message);
        return res.result.content;
    }
}
