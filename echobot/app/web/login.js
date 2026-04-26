// 负责登录页的注册、登录和登录后跳转逻辑。
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginTabButton = document.getElementById("login-tab-button");
const registerTabButton = document.getElementById("register-tab-button");
const authStatus = document.getElementById("auth-status");
const authModeTitle = document.getElementById("auth-mode-title");
const authModeDescription = document.getElementById("auth-mode-description");

const nextTarget = resolveNextTarget();
const modeCopy = {
    login: {
        title: "欢迎回来，继续这段对话。",
        description: "登录后会回到聊天主页，继续当前会话与舞台设置。",
        idleText: "请输入已有账号信息。",
        successText: "登录成功，正在回到对话空间…",
    },
    register: {
        title: "先为自己留一个安静的入口。",
        description: "注册完成后会直接进入聊天主页，开始属于你的新会话。",
        idleText: "注册完成后会直接进入聊天主页。",
        successText: "注册成功，正在进入对话空间…",
    },
};

loginTabButton.addEventListener("click", () => {
    switchMode("login");
});
registerTabButton.addEventListener("click", () => {
    switchMode("register");
});

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitAuthRequest({
        endpoint: "/api/auth/login",
        username: document.getElementById("login-username").value,
        password: document.getElementById("login-password").value,
        submitButton: document.getElementById("login-submit-button"),
        pendingText: "正在登录，请稍候…",
        successText: modeCopy.login.successText,
    });
});

registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitAuthRequest({
        endpoint: "/api/auth/register",
        username: document.getElementById("register-username").value,
        password: document.getElementById("register-password").value,
        submitButton: document.getElementById("register-submit-button"),
        pendingText: "正在注册，请稍候…",
        successText: modeCopy.register.successText,
    });
});

// 初始化时同步一次文案和页面状态。
switchMode("login");

function switchMode(mode) {
    const isLoginMode = mode === "login";
    const copy = isLoginMode ? modeCopy.login : modeCopy.register;

    document.body.dataset.authMode = mode;
    loginForm.hidden = !isLoginMode;
    registerForm.hidden = isLoginMode;
    loginTabButton.classList.toggle("is-active", isLoginMode);
    registerTabButton.classList.toggle("is-active", !isLoginMode);
    loginTabButton.setAttribute("aria-selected", String(isLoginMode));
    registerTabButton.setAttribute("aria-selected", String(!isLoginMode));
    authModeTitle.textContent = copy.title;
    authModeDescription.textContent = copy.description;
    authStatus.textContent = copy.idleText;
    authStatus.classList.remove("is-error", "is-success");
}

async function submitAuthRequest({
    endpoint,
    username,
    password,
    submitButton,
    pendingText,
    successText,
}) {
    const trimmedUsername = String(username || "").trim();
    const normalizedPassword = String(password || "").trim();
    if (!trimmedUsername || !normalizedPassword) {
        authStatus.textContent = "用户名和密码都需要填写。";
        authStatus.classList.remove("is-success");
        authStatus.classList.add("is-error");
        return;
    }

    const defaultButtonText = submitButton.textContent;
    submitButton.disabled = true;
    loginTabButton.disabled = true;
    registerTabButton.disabled = true;
    document.body.dataset.authPending = "true";
    submitButton.textContent = pendingText;
    authStatus.textContent = pendingText;
    authStatus.classList.remove("is-error", "is-success");

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({
                username: trimmedUsername,
                password: normalizedPassword,
            }),
        });

        if (!response.ok) {
            throw new Error(await readErrorMessage(response));
        }

        authStatus.textContent = successText;
        authStatus.classList.add("is-success");
        window.location.assign(nextTarget);
    } catch (error) {
        authStatus.textContent = error.message || "这一步暂时没有完成，请稍后再试。";
        authStatus.classList.remove("is-success");
        authStatus.classList.add("is-error");
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = defaultButtonText;
        loginTabButton.disabled = false;
        registerTabButton.disabled = false;
        delete document.body.dataset.authPending;
    }
}

async function readErrorMessage(response) {
    try {
        const payload = await response.json();
        if (payload && typeof payload.detail === "string") {
            return payload.detail;
        }
    } catch (_error) {
        return `${response.status} ${response.statusText}`;
    }
    return `${response.status} ${response.statusText}`;
}

function resolveNextTarget() {
    // 仅允许回到站内路径，避免开放重定向。
    const params = new URLSearchParams(window.location.search);
    const nextValue = String(params.get("next") || "").trim();
    if (nextValue.startsWith("/") && !nextValue.startsWith("//")) {
        return nextValue;
    }
    return "/web";
}
