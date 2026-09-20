// Small helpers shared by the page templates (conversation, roadmap, resume).
// Loaded via a plain <script> tag, so these are globals.

// el("div", { className: "card", text: "hi", role: "alert" }, child1, child2)
// Builds DOM nodes with textContent (never innerHTML), so server/LLM text can't inject markup.
function el(tag, props = {}, ...children) {
    const { className, text, ...attrs } = props;
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    node.append(...children);
    return node;
}

// Always resolves to { ok, status, data } - never throws.
// status 0 = network failure; data is null when the response body wasn't JSON
// (e.g. Flask's HTML 413 page for an oversized upload).
async function request(url, options) {
    try {
        const response = await fetch(url, options);
        let data = null;
        try {
            data = await response.json();
        } catch (_) {
            // Non-JSON body - fall through with data = null.
        }
        return { ok: response.ok, status: response.status, data };
    } catch (_) {
        return { ok: false, status: 0, data: null };
    }
}

// GET a JSON endpoint.
function getJson(url) {
    return request(url, { method: "GET" });
}

// POST, optionally with a JSON body.
function postJson(url, body) {
    const options = { method: "POST" };
    if (body) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(body);
    }
    return request(url, options);
}

// POST a FormData (multipart). The browser sets the Content-Type boundary itself,
// so no Content-Type header is set here.
function postForm(url, formData) {
    return request(url, { method: "POST", body: formData });
}
