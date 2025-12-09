// ---------- FLOATING CHAT WIDGET WITH DRAG + MINIMIZE + CLEAR + RESIZE (fixed) + PERSISTENCE ----------
(function () {

    const STORAGE_KEY = "xwiki_chat_history";
    const POSITION_KEY = "xwiki_chat_position";
    const MINIMIZED_KEY = "xwiki_chat_minimized";
    const SIZE_KEY = "xwiki_chat_size";

    // Create the floating container
    const chatContainer = document.createElement("div");
    chatContainer.id = "xwiki-rag-chatbox";

    chatContainer.innerHTML = `
        <div id="chatbox-header">
            <span>Ask the Knowledge Assistant</span>

            <span id="chatbox-minimize" 
                style="float:right; cursor:pointer; font-weight:bold; margin-right:5px;">
                –
            </span>

            <span id="chatbox-clear" 
                style="float:right; margin-left:10px; cursor:pointer; font-weight:bold;">
                🗑
            </span>

        </div>

        <div id="chatbox-messages"></div>

        <div id="chatbox-input-area">
            <input id="chatbox-input" type="text" placeholder="Ask a question..." />
            <button id="chatbox-send">Send</button>
        </div>

        <!-- Resize handles -->
        <div id="chatbox-resizer-br" class="chatbox-resizer"></div>
        <div id="chatbox-resizer-r" class="chatbox-resizer"></div>
        <div id="chatbox-resizer-b" class="chatbox-resizer"></div>
    `;

    // -------------------- CSS --------------------
    const style = document.createElement("style");
    style.textContent = `
        #xwiki-rag-chatbox {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 300px;
            height: 380px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            font-family: Arial, sans-serif;
            display: flex;
            flex-direction: column;
            z-index: 99999;
            overflow: visible;
            min-width: 240px;
            min-height: 200px;
            max-width: calc(100vw - 40px);
            max-height: calc(100vh - 40px);
        }

        #chatbox-header {
            background: #1872DE;
            color: white;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-radius: 10px 10px 0 0;
            cursor: move;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }

        #chatbox-header span { pointer-events: auto; }
        #chatbox-header > span:first-child { flex: 1; text-align: center; }

        #chatbox-messages {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            font-size: 14px;
        }

        .msg-user {
            background: #d7eaff;
            padding: 6px;
            margin: 5px 0;
            border-radius: 6px;
        }

        .msg-bot {
            background: #f1f1f1;
            padding: 6px;
            margin: 5px 0;
            border-radius: 6px;
        }

        #chatbox-input-area {
            display: flex;
            border-top: 1px solid #ccc;
        }

        #chatbox-input {
            flex: 1;
            padding: 8px;
            border: none;
            outline: none;
        }

        #chatbox-send {
            padding: 8px 12px;
            background: #1872DE;
            color: white;
            border: none;
            cursor: pointer;
        }

        /* Minimized Bar */
        #xwiki-chat-minimized-bar {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 180px;
            padding: 10px;
            background: #1872DE;
            color: white;
            border-radius: 8px;
            cursor: pointer;
            text-align: center;
            font-weight: bold;
            z-index: 99999;
            display: none;
        }

        /* Resizer handles */
        .chatbox-resizer {
            position: absolute;
            background: transparent;
            z-index: 100000;
        }

        /* Bottom-right corner handle (visible hit area) */
        #chatbox-resizer-br {
            width: 16px;
            height: 16px;
            right: 4px;
            bottom: 4px;
            cursor: se-resize;
        }

        /* Right edge handle (tall thin bar) */
        #chatbox-resizer-r {
            width: 8px;
            right: 0px;
            top: 36px;
            bottom: 36px;
            cursor: e-resize;
        }

        /* Bottom edge handle (wide thin bar) */
        #chatbox-resizer-b {
            height: 8px;
            left: 10px;
            right: 10px;
            bottom: 0px;
            cursor: s-resize;
        }

        /* small visible indicator for corner so user can see it (optional) */
        #chatbox-resizer-br::after {
            content: "";
            position: absolute;
            right: 3px;
            bottom: 3px;
            width: 10px;
            height: 10px;
            border-right: 2px solid rgba(0,0,0,0.12);
            border-bottom: 2px solid rgba(0,0,0,0.12);
            pointer-events: none;
            border-radius: 1px;
        }
    `;
    document.head.appendChild(style);

    document.body.appendChild(chatContainer);

    // Minimized bar creation
    const minimizedBar = document.createElement("div");
    minimizedBar.id = "xwiki-chat-minimized-bar";
    minimizedBar.textContent = "Open Assistant";
    document.body.appendChild(minimizedBar);

    // -------------------- DRAGGING --------------------
    let offsetX = 0, offsetY = 0, isDragging = false;
    const header = chatContainer.querySelector("#chatbox-header");

    header.addEventListener("mousedown", (e) => {
        // don't start drag if user clicked a control (minimize/clear)
        if (e.target && (e.target.id === "chatbox-minimize" || e.target.id === "chatbox-clear")) {
            return;
        }
        isDragging = true;
        // if not positioned yet, set left/top explicitly
        if (!chatContainer.style.left) {
            chatContainer.style.left = chatContainer.getBoundingClientRect().left + "px";
            chatContainer.style.top = chatContainer.getBoundingClientRect().top + "px";
        }
        offsetX = e.clientX - chatContainer.offsetLeft;
        offsetY = e.clientY - chatContainer.offsetTop;
        e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
        if (isDragging) {
            let newLeft = e.clientX - offsetX;
            let newTop = e.clientY - offsetY;

            // keep within viewport (simple clamp)
            const maxLeft = window.innerWidth - chatContainer.offsetWidth - 10;
            const maxTop = window.innerHeight - chatContainer.offsetHeight - 10;
            newLeft = Math.max(10, Math.min(maxLeft, newLeft));
            newTop = Math.max(10, Math.min(maxTop, newTop));

            chatContainer.style.left = newLeft + "px";
            chatContainer.style.top = newTop + "px";

            localStorage.setItem(POSITION_KEY, JSON.stringify({
                left: chatContainer.style.left,
                top: chatContainer.style.top
            }));
        }
    });

    document.addEventListener("mouseup", () => { isDragging = false; });

    // Restore previous position
    const savedPos = localStorage.getItem(POSITION_KEY);
    if (savedPos) {
        try {
            const pos = JSON.parse(savedPos);
            chatContainer.style.left = pos.left;
            chatContainer.style.top = pos.top;
            chatContainer.style.bottom = "auto";
            chatContainer.style.right = "auto";
        } catch (e) { /* ignore */ }
    }

    // -------------------- RESIZING (RIGHT, BOTTOM, BOTTOM-RIGHT) --------------------
    const resizerBR = document.getElementById("chatbox-resizer-br");
    const resizerR = document.getElementById("chatbox-resizer-r");
    const resizerB = document.getElementById("chatbox-resizer-b");

    let isResizing = false;
    let resizeType = null; // 'br' | 'r' | 'b'
    let startX = 0, startY = 0, startW = 0, startH = 0;

    function startResize(type, e) {
        isResizing = true;
        resizeType = type;
        startX = e.clientX;
        startY = e.clientY;
        startW = chatContainer.offsetWidth;
        startH = chatContainer.offsetHeight;

        // ensure container has explicit left/top so resizing behaves predictably
        if (!chatContainer.style.left) {
            chatContainer.style.left = chatContainer.getBoundingClientRect().left + "px";
            chatContainer.style.top = chatContainer.getBoundingClientRect().top + "px";
        }
        e.preventDefault();
        e.stopPropagation();
    }

    resizerBR.addEventListener("mousedown", (e) => startResize('br', e));
    resizerR.addEventListener("mousedown", (e) => startResize('r', e));
    resizerB.addEventListener("mousedown", (e) => startResize('b', e));

    document.addEventListener("mousemove", (e) => {
        if (!isResizing) return;

        const dx = e.clientX - startX;
        const dy = e.clientY - startY;

        let newW = startW;
        let newH = startH;

        if (resizeType === 'br') {
            newW = startW + dx;
            newH = startH + dy;
        } else if (resizeType === 'r') {
            newW = startW + dx;
        } else if (resizeType === 'b') {
            newH = startH + dy;
        }

        // apply min/max
        newW = Math.max(240, Math.min(window.innerWidth - 20, newW));
        newH = Math.max(200, Math.min(window.innerHeight - 20, newH));

        chatContainer.style.width = newW + "px";
        chatContainer.style.height = newH + "px";
    });

    document.addEventListener("mouseup", () => {
        if (isResizing) {
            // persist size
            localStorage.setItem(SIZE_KEY, JSON.stringify({
                width: chatContainer.offsetWidth,
                height: chatContainer.offsetHeight
            }));
        }
        isResizing = false;
        resizeType = null;
    });

    // Restore saved size
    const savedSize = localStorage.getItem(SIZE_KEY);
    if (savedSize) {
        try {
            const sz = JSON.parse(savedSize);
            if (sz.width) chatContainer.style.width = (Math.max(240, Math.min(window.innerWidth - 20, sz.width))) + "px";
            if (sz.height) chatContainer.style.height = (Math.max(200, Math.min(window.innerHeight - 20, sz.height))) + "px";
        } catch (e) { /* ignore */ }
    }

    // -------------------- MINIMIZE / MAXIMIZE --------------------
    const minimizeBtn = document.getElementById("chatbox-minimize");

    function minimize() {
        chatContainer.style.display = "none";
        minimizedBar.style.display = "block";
        localStorage.setItem(MINIMIZED_KEY, "true");
    }

    function maximize() {
        chatContainer.style.display = "flex";
        minimizedBar.style.display = "none";
        localStorage.setItem(MINIMIZED_KEY, "false");
    }

    minimizeBtn.onclick = minimize;
    minimizedBar.onclick = maximize;

    if (localStorage.getItem(MINIMIZED_KEY) === "true") minimize();

    // -------------------- CHAT HISTORY --------------------
    const messagesBox = document.getElementById("chatbox-messages");

    function appendMessage(text, role) {
        const div = document.createElement("div");
        div.className = role === "user" ? "msg-user" : "msg-bot";
        div.textContent = text;
        messagesBox.appendChild(div);
        messagesBox.scrollTop = messagesBox.scrollHeight;
    }

    function loadChatHistory() {
        const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        for (const msg of history) appendMessage(msg.text, msg.role);
    }

    function saveMessage(msg, role) {
        const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        history.push({ role, text: msg });
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }

    loadChatHistory();

    // -------------------- CLEAR CHAT BUTTON --------------------
    const clearBtn = document.getElementById("chatbox-clear");
    clearBtn.onclick = function () {
        localStorage.removeItem(STORAGE_KEY);
        messagesBox.innerHTML = "";
        appendMessage("🧹 Chat cleared.", "bot");
    };

    // -------------------- BACKEND MESSAGE SENDING --------------------
    document.getElementById("chatbox-send").onclick = async function () {
        const input = document.getElementById("chatbox-input");
        const text = input.value.trim();
        if (!text) return;

        appendMessage(text, "user");
        saveMessage(text, "user");
        input.value = "";

        await sendToBackend(text);
    };

    async function sendToBackend(query) {
        appendMessage("Thinking...", "bot");

        try {
            const response = await fetch("http://localhost:9100/rag_query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query, top_k: 3 })
            });

            const data = await response.json();

            messagesBox.lastChild.remove();
            appendMessage(data.answer, "bot");
            saveMessage(data.answer, "bot");

        } catch (err) {
            messagesBox.lastChild.remove();
            appendMessage("⚠️ Error: Could not reach backend.", "bot");
            saveMessage("⚠️ Error: Could not reach backend.", "bot");
        }
    }

    document.getElementById("chatbox-input").addEventListener("keydown", async function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            document.getElementById("chatbox-send").click();
        }
    });

})();
