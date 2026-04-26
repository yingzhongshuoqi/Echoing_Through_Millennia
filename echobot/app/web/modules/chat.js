import { buildUserMessageContent } from "./content.js";
import { DEFAULT_SESSION_NAME, DOM, UI_STATE } from "./state.js";

const MAX_COMPOSER_IMAGES = 6;

export function createChatModule(deps) {
    const {
        addMessage,
        applySessionSummaries,
        cancelChatJob,
        createSpeechSession,
        drainVoicePromptQueue,
        ensureAudioContextReady,
        finalizeSpeechSession,
        normalizeSessionName,
        queueSpeechSessionText,
        removeMessage,
        requestChatJob,
        requestChatJobTrace,
        requestChatStream,
        requestSessionSummaries,
        resetTracePanel,
        setActiveBackgroundJob,
        setChatBusy,
        setRunStatus,
        speakText,
        startTracePanel,
        stopSpeechPlayback,
        syncCurrentSessionFromServer,
        applyTracePayload,
        updateMessage,
    } = deps;

    async function handleChatSubmit(event) {
        event.preventDefault();
        if (UI_STATE.chatBusy) {
            return;
        }

        const prompt = String(DOM.promptInput?.value || "").trim();
        const composerImages = [...(UI_STATE.composerImages || [])];
        if (!prompt && composerImages.length === 0) {
            return;
        }

        await ensureAudioContextReady();

        const sessionName = normalizeSessionName(
            UI_STATE.currentSessionName || DEFAULT_SESSION_NAME,
        );
        UI_STATE.currentSessionName = sessionName;
        DOM.sessionLabel.textContent = `会话：${sessionName}`;
        window.localStorage.setItem("echobot.web.session", sessionName);

        DOM.promptInput.value = "";
        clearComposerImages();
        stopSpeechPlayback();
        setActiveBackgroundJob("");
        resetTracePanel();
        setChatBusy(true);
        const speechSession = UI_STATE.ttsEnabled ? createSpeechSession() : null;
        setRunStatus("正在整理回复…");

        addMessage(
            "user",
            buildUserMessageContent(
                prompt,
                composerImages.map((image) => image.dataUrl),
            ),
            "你",
            {
                renderMode: "plain",
                showMeta: true,
            },
        );
        let assistantMessageId = addMessage(
            "assistant",
            "...",
            "回应生成中",
            {
                renderMode: "plain",
                showMeta: true,
                state: "loading",
            },
        );
        let streamedText = "";

        try {
            const response = await requestChatStream(
                {
                    prompt: prompt,
                    session_name: sessionName,
                    role_name: UI_STATE.currentRoleName || "default",
                    route_mode: UI_STATE.currentRouteMode || "auto",
                    images: composerImages.map((image) => ({
                        data_url: image.dataUrl,
                    })),
                },
                {
                    onChunk(delta) {
                        streamedText += delta;
                        updateMessage(
                            assistantMessageId,
                            streamedText || "...",
                            "回应生成中",
                            {
                                renderMode: "plain",
                                showMeta: true,
                                state: "loading",
                            },
                        );
                        queueSpeechSessionText(speechSession, delta);
                    },
                },
            );

            if (response.session_name) {
                UI_STATE.currentSessionName = normalizeSessionName(response.session_name);
                DOM.sessionLabel.textContent = `会话: ${UI_STATE.currentSessionName}`;
                window.localStorage.setItem("echobot.web.session", UI_STATE.currentSessionName);
            }
            UI_STATE.currentRoleName = response.role_name || UI_STATE.currentRoleName;

            const immediateText = String(response.response || streamedText || "").trim();
            const hideImmediateReply = Boolean(
                response.job_id
                && response.status === "running"
                && !immediateText,
            );
            let finalText = immediateText || "处理中...";
            let speakFinalText = true;
            const startupSpeech = hideImmediateReply
                ? Promise.resolve()
                : finalizeSpeechSession(speechSession, finalText);
            if (hideImmediateReply) {
                removeMessage(assistantMessageId);
                assistantMessageId = "";
                finalText = "";
            } else {
                updateMessage(
                    assistantMessageId,
                    finalText,
                    response.completed ? "Echo" : "处理中",
                );
            }

            if (response.emotion || response.relic) {
                _renderRelicEmotionCard(assistantMessageId, response.emotion, response.relic);
            }

            if (response.job_id && response.status === "running") {
                setActiveBackgroundJob(response.job_id);
                setRunStatus("后台任务正在继续整理回复…");
                startTracePanel(response.job_id);

                const finalJob = await pollChatJob(response.job_id);
                finalText = finalJob.response || finalText || "任务已结束，但没有返回内容。";
                if (assistantMessageId) {
                    updateMessage(assistantMessageId, finalText, "Echo", {
                        showMeta: true,
                    });
                } else {
                    assistantMessageId = addMessage("assistant", finalText, "Echo", {
                        showMeta: true,
                    });
                }

                await startupSpeech;
                if (finalText === immediateText || finalJob.status === "cancelled") {
                    speakFinalText = false;
                }

                if (finalJob.status === "cancelled") {
                    setRunStatus("后台任务已停止");
                } else if (finalJob.status === "failed") {
                    setRunStatus("后台任务失败");
                } else {
                    setRunStatus("回复已完成");
                }
            } else {
                speakFinalText = false;
                setRunStatus("回复已完成");
            }

            if (UI_STATE.ttsEnabled && speakFinalText && finalText.trim()) {
                await speakText(finalText);
            }

            try {
                applySessionSummaries(await requestSessionSummaries());
            } catch (sessionError) {
                console.error("Failed to refresh session list after chat", sessionError);
            }
            await syncCurrentSessionFromServer({
                force: true,
                announceNewMessages: false,
            });
        } catch (error) {
            console.error(error);
            stopSpeechPlayback();
            if (assistantMessageId && !streamedText.trim()) {
                removeMessage(assistantMessageId);
            }
            addMessage("system", `请求失败：${error.message || error}`, "状态");
            setRunStatus(error.message || "请求失败");
        } finally {
            setActiveBackgroundJob("");
            setChatBusy(false);
            void drainVoicePromptQueue();
        }
    }

    async function pollChatJob(jobId) {
        const maxAttempts = 240;

        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
            const [payload, tracePayload] = await Promise.all([
                requestChatJob(jobId),
                loadChatJobTrace(jobId),
            ]);
            if (tracePayload) {
                applyTracePayload(jobId, tracePayload);
            }
            if (payload.status !== "running") {
                return payload;
            }
            await new Promise((resolve) => {
                window.setTimeout(resolve, 1000);
            });
        }

        throw new Error("Agent 后台任务等待超时");
    }

    async function loadChatJobTrace(jobId) {
        try {
            return await requestChatJobTrace(jobId);
        } catch (error) {
            console.warn("Failed to load agent trace", error);
            return null;
        }
    }

    async function handleStopBackgroundJob() {
        const jobId = UI_STATE.activeChatJobId;
        if (!jobId) {
            return;
        }

        if (DOM.stopAgentButton) {
            DOM.stopAgentButton.disabled = true;
        }
        setRunStatus("正在停止后台任务…");

        try {
            const payload = await cancelChatJob(jobId);
            if (payload.status === "cancelled") {
                setRunStatus("后台任务已停止");
                return;
            }
            if (payload.status === "completed") {
                setRunStatus("后台任务已完成");
                return;
            }
            if (payload.status === "failed") {
                setRunStatus("后台任务已失败");
                return;
            }

            if (DOM.stopAgentButton) {
                DOM.stopAgentButton.disabled = false;
            }
        } catch (error) {
            console.error(error);
            if (DOM.stopAgentButton) {
                DOM.stopAgentButton.disabled = false;
            }
            addMessage("system", `停止后台任务失败：${error.message || error}`, "状态");
            setRunStatus(error.message || "停止后台任务失败");
        }
    }

    function handleComposerImageButtonClick() {
        if (
            !DOM.composerImageInput
            || UI_STATE.chatBusy
            || UI_STATE.activeChatJobId
        ) {
            return;
        }
        DOM.composerImageInput.click();
    }

    async function handleComposerImageInputChange() {
        if (!DOM.composerImageInput) {
            return;
        }

        const selectedFiles = Array.from(DOM.composerImageInput.files || []);
        DOM.composerImageInput.value = "";
        if (!selectedFiles.length) {
            return;
        }

        try {
            const nextImages = await readComposerImages(selectedFiles);
            if (!nextImages.length) {
                return;
            }

            const existingImages = UI_STATE.composerImages || [];
            const availableSlots = Math.max(
                MAX_COMPOSER_IMAGES - existingImages.length,
                0,
            );
            if (availableSlots <= 0) {
                setRunStatus(`最多只能附加 ${MAX_COMPOSER_IMAGES} 张图片`);
                return;
            }

            const acceptedImages = nextImages.slice(0, availableSlots);
            if (acceptedImages.length < nextImages.length) {
                setRunStatus(`最多只能附加 ${MAX_COMPOSER_IMAGES} 张图片`);
            }
            UI_STATE.composerImages = [...existingImages, ...acceptedImages];
            renderComposerImages();
        } catch (error) {
            console.error("Failed to load composer images", error);
            setRunStatus(error.message || "图片加载失败");
        }
    }

    function handleComposerImagesClick(event) {
        const removeButton = event.target.closest("[data-composer-image-id]");
        if (!removeButton) {
            return;
        }

        const imageId = String(removeButton.dataset.composerImageId || "").trim();
        if (!imageId) {
            return;
        }

        UI_STATE.composerImages = (UI_STATE.composerImages || []).filter(
            (image) => image.id !== imageId,
        );
        renderComposerImages();
    }

    function refreshComposerImages() {
        renderComposerImages();
    }

    return {
        handleChatSubmit: handleChatSubmit,
        handleStopBackgroundJob: handleStopBackgroundJob,
        handleComposerImageButtonClick: handleComposerImageButtonClick,
        handleComposerImageInputChange: handleComposerImageInputChange,
        handleComposerImagesClick: handleComposerImagesClick,
        refreshComposerImages: refreshComposerImages,
    };
}

function clearComposerImages() {
    UI_STATE.composerImages = [];
    renderComposerImages();
}

async function readComposerImages(files) {
    const imageFiles = files.filter((file) => String(file.type || "").startsWith("image/"));
    const nextImages = await Promise.all(
        imageFiles.map(async (file, index) => ({
            id: `img-${Date.now()}-${index}-${Math.random().toString(16).slice(2, 8)}`,
            name: file.name || "image",
            dataUrl: await readFileAsDataUrl(file),
        })),
    );
    return nextImages.filter((image) => String(image.dataUrl || "").trim());
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.addEventListener("load", () => {
            resolve(String(reader.result || ""));
        });
        reader.addEventListener("error", () => {
            reject(reader.error || new Error("Failed to read image file."));
        });
        reader.readAsDataURL(file);
    });
}

// Plutchik 标准色谱
const PLUTCHIK_COLORS = {
    joy: "#FFEB3B", trust: "#8BC34A", fear: "#4CAF50", surprise: "#00BCD4",
    sadness: "#2196F3", disgust: "#9C27B0", anger: "#F44336", anticipation: "#FF9800",
};

function _renderRelicEmotionCard(messageId, emotion, relic) {
    if (!messageId) return;
    const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!messageEl) return;

    const container = document.createElement("div");
    container.className = "relic-emotion-container";

    if (emotion) {
        // ── Plutchik 主导情绪 badges ──
        if (emotion.dominant_emotions && emotion.dominant_emotions.length > 0) {
            const emotionGroup = document.createElement("div");
            emotionGroup.className = "plutchik-emotions";

            for (const de of emotion.dominant_emotions.slice(0, 3)) {
                const badge = document.createElement("span");
                badge.className = "emotion-badge plutchik-badge";
                const color = PLUTCHIK_COLORS[de.emotion] || de.color || "#888";
                badge.style.setProperty("--plutchik-color", color);
                badge.textContent = de.intensity_name_cn || de.cn || de.emotion;
                badge.title = `${de.cn || ""} (${de.emotion}) — ${Math.round((de.score || 0) * 100)}%`;
                emotionGroup.appendChild(badge);
            }
            container.appendChild(emotionGroup);
        } else if (emotion.primary) {
            // 兼容旧格式
            const badge = document.createElement("span");
            badge.className = "emotion-badge";
            const intensity = emotion.intensity || 5;
            badge.textContent = `${emotion.primary}${emotion.secondary ? " · " + emotion.secondary : ""} (${intensity}/10)`;
            badge.title = emotion.need ? `需求: ${emotion.need}` : "";
            if (intensity >= 7) badge.classList.add("emotion-high");
            else if (intensity >= 4) badge.classList.add("emotion-mid");
            else badge.classList.add("emotion-low");
            container.appendChild(badge);
        }

        // ── 复合情绪（Dyads）──
        if (emotion.active_dyads && emotion.active_dyads.length > 0) {
            const dyadGroup = document.createElement("div");
            dyadGroup.className = "dyad-badges";
            for (const dyad of emotion.active_dyads.slice(0, 3)) {
                const badge = document.createElement("span");
                badge.className = "dyad-badge";
                badge.textContent = dyad.name_cn || dyad.name_en || "";
                badge.title = `${dyad.name_en || ""} (${dyad.type || ""}) — ${(dyad.components || []).join("+")}`;
                dyadGroup.appendChild(badge);
            }
            container.appendChild(dyadGroup);
        }

        // ── 强度级别 ──
        if (emotion.intensity_level) {
            const intensityEl = document.createElement("span");
            intensityEl.className = `intensity-indicator intensity-${emotion.intensity_level}`;
            const levelNames = { mild: "平和", basic: "中等", intense: "强烈" };
            intensityEl.textContent = levelNames[emotion.intensity_level] || emotion.intensity_level;
            container.appendChild(intensityEl);
        }

        // ── 对话阶段 ──
        if (emotion.phase) {
            const phaseLabel = document.createElement("span");
            phaseLabel.className = "emotion-phase";
            const phaseNames = { listening: "倾听", resonance: "共鸣", guiding: "引导", elevation: "升华" };
            phaseLabel.textContent = phaseNames[emotion.phase] || emotion.phase;
            container.appendChild(phaseLabel);
        }

        // ── 心理需求 ──
        if (emotion.need) {
            const needEl = document.createElement("span");
            needEl.className = "emotion-need";
            needEl.textContent = emotion.need;
            container.appendChild(needEl);
        }
    }

    if (relic) {
        const card = document.createElement("div");
        card.className = "relic-card";
        card.innerHTML = `
            <div class="relic-card-header">
                <span class="relic-icon">🏺</span>
                <span class="relic-name">${_escapeHtml(relic.name || "")}</span>
                <span class="relic-dynasty">${_escapeHtml(relic.dynasty || "")}</span>
                ${relic.score ? `<span class="relic-score">匹配 ${Math.round((relic.score || 0) * 100)}%</span>` : ""}
            </div>
            ${relic.description ? `<div class="relic-description">${_escapeHtml(relic.description).slice(0, 120)}${(relic.description || "").length > 120 ? "..." : ""}</div>` : ""}
        `;
        container.appendChild(card);
    }

    if (container.children.length > 0) {
        messageEl.appendChild(container);
    }
}

function _escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function renderComposerImages() {
    if (!DOM.composerImages) {
        return;
    }

    const composerImages = Array.isArray(UI_STATE.composerImages)
        ? UI_STATE.composerImages
        : [];
    DOM.composerImages.innerHTML = "";
    DOM.composerImages.hidden = composerImages.length === 0;

    composerImages.forEach((image) => {
        const card = document.createElement("div");
        card.className = "composer-image-chip";

        const preview = document.createElement("img");
        preview.className = "composer-image-thumb";
        preview.src = image.dataUrl;
        preview.alt = image.name || "Selected image";
        preview.loading = "lazy";
        card.appendChild(preview);

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "composer-image-remove";
        removeButton.dataset.composerImageId = image.id;
        removeButton.textContent = "×";
        removeButton.title = "移除图片";
        removeButton.disabled = UI_STATE.chatBusy || Boolean(UI_STATE.activeChatJobId);
        card.appendChild(removeButton);

        DOM.composerImages.appendChild(card);
    });
}
