import { SimpleMCPClient } from './simple_mcp_client.js';

const ui = {
    authPanel: document.getElementById('authPanel'),
    mainApp: document.getElementById('mainApp'),
    usernameInput: document.getElementById('usernameInput'),
    roleInput: document.getElementById('roleInput'),
    loginBtn: document.getElementById('loginBtn'),
    statusBadge: document.getElementById('statusBadge'),
    toolsList: document.getElementById('toolsList'),
    logsArea: document.getElementById('logsArea'),
    activeToolName: document.getElementById('activeToolName'),
    formBody: document.getElementById('formBody'),
    jobsTracker: document.getElementById('jobsTracker'),
    jobIdLabel: document.getElementById('jobIdLabel'),
    pollJobBtn: document.getElementById('pollJobBtn'),
};

let client = null;
let activeJobId = null;

function log(msg, type = 'sys') {
    const el = document.createElement('div');
    el.className = `log-entry log-${type}`;
    el.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
    ui.logsArea.appendChild(el);
    ui.logsArea.scrollTop = ui.logsArea.scrollHeight;
}

ui.loginBtn.addEventListener('click', async () => {
    const username = ui.usernameInput.value.trim();
    const role = ui.roleInput.value;
    if (!username) return alert('Enter a username');

    ui.loginBtn.disabled = true;
    ui.loginBtn.innerText = 'Acquiring JWT...';

    const serverUrl = window.location.origin;

    try {
        // Step 1: Login to get signed JWT
        log(`Authenticating ${username} as ${role}...`, 'sys');
        const loginRes = await fetch(`${serverUrl}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, role })
        });

        if (!loginRes.ok) throw new Error('Login failed');
        const { access_token } = await loginRes.json();
        log(`Acquired signed JWT! Role: ${role}`, 'success');

        ui.loginBtn.innerText = 'Connecting over SSE...';
        client = new SimpleMCPClient(serverUrl, access_token);
        client.onLog = (msg) => log(msg, 'sys');

        await client.connect();
        ui.authPanel.classList.add('hidden');
        ui.mainApp.classList.remove('hidden');
        ui.statusBadge.style.display = 'block';

        loadTools();
    } catch (err) {
        log(`Connection failed: ${err.message}`, 'error');
        ui.loginBtn.disabled = false;
        ui.loginBtn.innerText = 'Login & Connect';
    }
});

async function loadTools() {
    log('Fetching Agent-Native Tool Contracts...', 'sys');
    try {
        const tools = await client.listTools();
        ui.toolsList.innerHTML = '';

        tools.forEach(tool => {
            const card = document.createElement('div');
            card.className = 'tool-card';
            card.innerHTML = `<h3>${tool.name}</h3><p>${tool.description}</p>`;
            card.addEventListener('click', () => selectTool(tool));
            ui.toolsList.appendChild(card);
        });
        log(`Loaded ${tools.length} strongly typed tools.`, 'success');
    } catch (err) {
        log(`Failed listing tools: ${err.message}`, 'error');
    }
}

function selectTool(tool) {
    ui.activeToolName.innerText = `Execute: ${tool.name}`;
    ui.formBody.innerHTML = '';

    // Dynamically build the form based on Pydantic JSON schema
    const props = tool.inputSchema?.properties || {};
    const argsData = {};

    Object.keys(props).forEach(key => {
        const schema = props[key];
        const group = document.createElement('div');
        group.className = 'form-group';

        group.innerHTML = `<label>${key} <span style="color:#8b949e">(${schema.type})</span> - ${schema.description}</label>`;

        const input = document.createElement('input');
        input.type = schema.type === 'integer' ? 'number' : 'text';

        // Smart defaults for demo
        if (schema.type === 'integer') input.value = 5;
        else if (key === 'job_id' && activeJobId) input.value = activeJobId;
        else input.value = `Example ${key}`;

        input.addEventListener('change', (e) => {
            argsData[key] = schema.type === 'integer' ? parseInt(e.target.value) : e.target.value;
        });

        // init data
        argsData[key] = schema.type === 'integer' ? parseInt(input.value) : input.value;
        group.appendChild(input);
        ui.formBody.appendChild(group);
    });

    // Ensure form state updates on submit incase user didn't fire 'change' event on fields
    const btn = document.createElement('button');
    btn.innerText = 'Invoke via MCP';
    btn.style.marginTop = '10px';
    btn.onclick = async () => {
        // Collect latest values before sending
        Array.from(ui.formBody.querySelectorAll('input')).forEach((inputEl, idx) => {
            const key = Object.keys(props)[idx];
            argsData[key] = props[key].type === 'integer' ? parseInt(inputEl.value) : inputEl.value;
        });

        log(`Executing [${tool.name}] ...`, 'tool');
        btn.disabled = true;
        try {
            const result = await client.callTool(tool.name, argsData);

            // Render the complex MCP types TextContent
            const textResponse = result.find(c => c.type === 'text')?.text || JSON.stringify(result);
            log(`Result:\n${textResponse}`, 'success');

            // Extract active job ID if user just started a task
            if (tool.name === 'start_long_running_task' && textResponse.includes('track progress: ')) {
                activeJobId = textResponse.split('track progress: ')[1].trim();
                ui.jobIdLabel.innerText = activeJobId;
                ui.jobsTracker.classList.remove('hidden');
            }

        } catch (err) {
            log(`Execution Error: ${err}`, 'error');
        } finally {
            btn.disabled = false;
        }
    };

    ui.formBody.appendChild(btn);
}

// Global polling hook
ui.pollJobBtn.addEventListener('click', async () => {
    if (!activeJobId) return;
    log(`Polling job status for ${activeJobId}...`, 'tool');
    ui.pollJobBtn.disabled = true;
    try {
        const result = await client.callTool('check_task_status', { job_id: activeJobId });
        const textResponse = result.find(c => c.type === 'text')?.text || JSON.stringify(result);
        log(`Status Check:\n${textResponse}`, 'success');

        if (textResponse.includes('FINAL RESULT') || textResponse.includes('ERROR:')) {
            ui.jobsTracker.classList.add('hidden'); // cleanup UI
            activeJobId = null;
        }
    } catch (err) {
        log(`Status Error: ${err}`, 'error');
    } finally {
        ui.pollJobBtn.disabled = false;
    }
});
