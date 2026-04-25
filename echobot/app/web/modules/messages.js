import { DOM, UI_STATE } from "./state.js";
import {
    IMAGE_URL_CONTENT_BLOCK_TYPE,
    TEXT_CONTENT_BLOCK_TYPE,
    normalizeMessageContent,
} from "./content.js";
import {
    clearMathTypesetting,
    scheduleMathTypesetting,
} from "./math.js";
import { buildMarkdownFragment } from "./markdown.js";

let pendingScrollFrameId = 0;
let messagesEmptyState = null;

const DEFAULT_EMPTY_STATE = {
    eyebrow: "当前会话",
    title: "从一段轻声的提问开始。",
    description: "这里会保留你的对话、流式回复和文化陪伴内容。你可以先说近况，也可以直接提出想被回应的情绪。",
    tips: [
        "可以描述今天最明显的一种感受。",
        "也可以补充一个困扰你的具体场景。",
    ],
};

export function addMessage(kind, content, label, options = {}) {
    const messageId = `msg-${++UI_STATE.messageCounter}`;
    const container = document.createElement("article");
    container.className = `message message-${kind}`;
    container.dataset.messageId = messageId;
    container.dataset.messageKind = kind;
    container.setAttribute("role", kind === "system" ? "status" : "group");
    container.setAttribute("aria-label", resolveMessageAriaLabel(kind, label));
    if (kind === "system") {
        container.setAttribute("aria-live", "polite");
    }

    messagesEmptyState = null;
    clearMessagesEmptyState();
    applyMessageState(container, options);

    const body = document.createElement("div");
    body.className = "message-text";
    renderMessageBody(body, kind, content, options);

    container.appendChild(body);
    syncMessageMeta(container, label, options);
    DOM.messages.appendChild(container);
    scheduleMathTypesetting(body);
    scheduleMessagesScrollToBottom();
    return messageId;
}

export function addSystemMessage(text, options = {}) {
    addMessage("system", text, "状态", {
        renderMode: "plain",
        ...options,
    });
}

export function updateMessage(messageId, content, label, options = {}) {
    const container = DOM.messages.querySelector(`[data-message-id="${messageId}"]`);
    if (!container) {
        return;
    }

    const body = container.querySelector(".message-text");
    const kind = container.dataset.messageKind || "assistant";
    container.setAttribute("aria-label", resolveMessageAriaLabel(kind, label));
    applyMessageState(container, options);
    syncMessageMeta(container, label, options);
    if (body) {
        renderMessageBody(body, kind, content, options);
        scheduleMathTypesetting(body);
    }
    scheduleMessagesScrollToBottom();
}

export function clearMessages() {
    clearMathTypesetting(DOM.messages);
    DOM.messages.innerHTML = "";
    UI_STATE.messageCounter = 0;
}

export function showMessagesEmptyState(options = {}) {
    messagesEmptyState = {
        ...DEFAULT_EMPTY_STATE,
        ...(options || {}),
    };
    renderMessagesEmptyState();
}

export function scheduleMessagesScrollToBottom() {
    if (!DOM.messages || pendingScrollFrameId) {
        return;
    }

    pendingScrollFrameId = window.requestAnimationFrame(() => {
        pendingScrollFrameId = 0;
        scrollMessagesToBottom();
    });
}

export function removeMessage(messageId) {
    const container = DOM.messages.querySelector(`[data-message-id="${messageId}"]`);
    if (!container) {
        return;
    }
    clearMathTypesetting(container);
    container.remove();
    syncMessagesEmptyState();
}

export function initializeMessageInteractions() {
    if (DOM.messages) {
        DOM.messages.addEventListener("click", handleMessageAreaClick);
    }
    if (DOM.messageImageDialogClose) {
        DOM.messageImageDialogClose.addEventListener("click", closeMessageImagePreview);
    }
    if (DOM.messageImageDialog) {
        DOM.messageImageDialog.addEventListener("click", handleMessageImageDialogClick);
        DOM.messageImageDialog.addEventListener("close", resetMessageImagePreview);
        DOM.messageImageDialog.addEventListener("cancel", () => {
            resetMessageImagePreview();
        });
    }
}

function syncMessageMeta(container, label, options = {}) {
    const existingMeta = container.querySelector(".message-meta");
    const body = container.querySelector(".message-text");

    if (!options.showMeta) {
        if (existingMeta) {
            existingMeta.remove();
        }
        return;
    }

    const meta = existingMeta || document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = String(label || "");

    if (!existingMeta) {
        if (body) {
            container.insertBefore(meta, body);
        } else {
            container.appendChild(meta);
        }
    }
}

function applyMessageState(container, options = {}) {
    const state = String(options.state || "ready").trim().toLowerCase();
    const tone = String(options.tone || "").trim().toLowerCase();

    container.dataset.messageState = state || "ready";
    if (tone) {
        container.dataset.messageTone = tone;
    } else {
        delete container.dataset.messageTone;
    }

    if (state === "loading") {
        container.setAttribute("aria-busy", "true");
    } else {
        container.removeAttribute("aria-busy");
    }
}

function renderMessagesEmptyState() {
    if (!DOM.messages) {
        return;
    }

    clearMessagesEmptyState();
    if (DOM.messages.querySelector(".message")) {
        return;
    }

    const state = messagesEmptyState || DEFAULT_EMPTY_STATE;
    const container = document.createElement("section");
    container.className = "messages-empty-state";
    container.dataset.emptyState = "true";

    const eyebrow = document.createElement("p");
    eyebrow.className = "messages-empty-eyebrow";
    eyebrow.textContent = String(state.eyebrow || DEFAULT_EMPTY_STATE.eyebrow);

    const title = document.createElement("h3");
    title.className = "messages-empty-title";
    title.textContent = String(state.title || DEFAULT_EMPTY_STATE.title);

    const description = document.createElement("p");
    description.className = "messages-empty-description";
    description.textContent = String(state.description || DEFAULT_EMPTY_STATE.description);

    container.appendChild(eyebrow);
    container.appendChild(title);
    container.appendChild(description);

    const tips = Array.isArray(state.tips) ? state.tips.filter(Boolean) : [];
    if (tips.length > 0) {
        const tipsList = document.createElement("ul");
        tipsList.className = "messages-empty-tips";
        tips.forEach((tip) => {
            const item = document.createElement("li");
            item.textContent = String(tip);
            tipsList.appendChild(item);
        });
        container.appendChild(tipsList);
    }

    DOM.messages.appendChild(container);
}

function clearMessagesEmptyState() {
    const placeholder = DOM.messages?.querySelector("[data-empty-state='true']");
    if (placeholder) {
        placeholder.remove();
    }
}

function syncMessagesEmptyState() {
    if (!DOM.messages) {
        return;
    }
    if (DOM.messages.querySelector(".message")) {
        clearMessagesEmptyState();
        return;
    }
    if (messagesEmptyState) {
        renderMessagesEmptyState();
    }
}

function scrollMessagesToBottom() {
    if (!DOM.messages) {
        return;
    }

    DOM.messages.scrollTop = DOM.messages.scrollHeight;
}

function resolveMessageAriaLabel(kind, label) {
    const customLabel = String(label || "").trim();
    if (customLabel) {
        return customLabel;
    }

    if (kind === "user") {
        return "你的消息";
    }
    if (kind === "assistant") {
        return "Echo 回复";
    }
    if (kind === "system") {
        return "状态提示";
    }
    return "消息";
}

function renderMessageBody(element, kind, content, options = {}) {
    clearMathTypesetting(element);
    const normalizedContent = normalizeMessageContent(content);
    if (Array.isArray(normalizedContent)) {
        renderStructuredBody(element, kind, normalizedContent, options);
        return;
    }

    const renderMode = resolveMessageRenderMode(kind, options);
    if (renderMode === "markdown") {
        renderMarkdownBody(element, normalizedContent);
        return;
    }
    renderPlainTextBody(element, normalizedContent, options);
}

function resolveMessageRenderMode(kind, options) {
    if (options.renderMode === "markdown") {
        return "markdown";
    }
    if (options.renderMode === "plain") {
        return "plain";
    }
    return kind === "assistant" ? "markdown" : "plain";
}

function renderPlainTextBody(element, text, options = {}) {
    const safeText = String(text || "");
    element.className = "message-text message-text-plain";

    if (options.state === "loading") {
        const content = document.createElement("div");
        content.className = "message-loading-inline";
        if (safeText.trim()) {
            const label = document.createElement("span");
            label.className = "message-loading-text";
            label.textContent = safeText;
            content.appendChild(label);
        }
        content.appendChild(buildLoadingDots());
        element.replaceChildren(content);
        return;
    }

    element.textContent = safeText;
}

function renderMarkdownBody(element, text) {
    element.className = "message-text message-text-markdown";
    element.replaceChildren(buildMarkdownFragment(String(text || "")));
}

function renderStructuredBody(element, kind, contentBlocks, options) {
    const renderMode = resolveMessageRenderMode(kind, options);
    const fragment = document.createDocumentFragment();

    contentBlocks.forEach((block) => {
        const blockType = String(block.type || "").trim();
        if (blockType === TEXT_CONTENT_BLOCK_TYPE) {
            fragment.appendChild(
                buildTextBlock(
                    String(block.text || ""),
                    renderMode,
                ),
            );
            return;
        }

        if (blockType === IMAGE_URL_CONTENT_BLOCK_TYPE) {
            const imageUrl = String(block.image_url?.url || "").trim();
            if (imageUrl) {
                fragment.appendChild(buildImageBlock(imageUrl));
            }
            return;
        }

        if (blockType) {
            fragment.appendChild(buildTextBlock(`[${blockType}]`, "plain"));
        }
    });

    element.className = "message-text message-text-structured";
    if (!fragment.childNodes.length) {
        element.textContent = "";
        return;
    }
    element.replaceChildren(fragment);
}

function buildTextBlock(text, renderMode) {
    const block = document.createElement("div");
    block.className = "message-block message-block-text";
    if (renderMode === "markdown") {
        block.classList.add("message-text-markdown");
        block.replaceChildren(buildMarkdownFragment(String(text || "")));
        return block;
    }

    block.classList.add("message-text-plain");
    block.textContent = String(text || "");
    return block;
}

function buildImageBlock(imageUrl) {
    const block = document.createElement("div");
    block.className = "message-block message-block-image";

    const previewButton = document.createElement("button");
    previewButton.type = "button";
    previewButton.className = "message-image-link";
    previewButton.dataset.imagePreview = "true";
    previewButton.dataset.imageUrl = imageUrl;
    previewButton.title = "点击预览图片";
    previewButton.setAttribute("aria-label", "预览图片");

    const image = document.createElement("img");
    image.className = "message-image";
    image.src = imageUrl;
    image.alt = "Attached image";
    image.loading = "lazy";

    previewButton.appendChild(image);
    block.appendChild(previewButton);
    return block;
}

function buildLoadingDots() {
    const dots = document.createElement("span");
    dots.className = "message-streaming-dots";
    dots.setAttribute("aria-hidden", "true");
    dots.innerHTML = "<span></span><span></span><span></span>";
    return dots;
}

function handleMessageAreaClick(event) {
    const previewTrigger = event.target.closest(".message-image-link[data-image-preview='true']");
    if (!previewTrigger || !DOM.messageImageDialog) {
        return;
    }

    const imageUrl = String(previewTrigger.dataset.imageUrl || "").trim();
    if (!imageUrl) {
        return;
    }

    openMessageImagePreview(imageUrl);
}

function openMessageImagePreview(imageUrl) {
    if (!DOM.messageImageDialog || !DOM.messageImageDialogImage) {
        return;
    }

    DOM.messageImageDialogImage.src = imageUrl;

    if (!DOM.messageImageDialog.open) {
        DOM.messageImageDialog.showModal();
    }
}

function closeMessageImagePreview() {
    if (DOM.messageImageDialog?.open) {
        DOM.messageImageDialog.close();
    }
}

function handleMessageImageDialogClick(event) {
    if (event.target === DOM.messageImageDialog) {
        closeMessageImagePreview();
    }
}

function resetMessageImagePreview() {
    if (DOM.messageImageDialogImage) {
        DOM.messageImageDialogImage.removeAttribute("src");
    }
}
