// 负责登录页的注册、登录和登录后跳转逻辑。
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginTabButton = document.getElementById("login-tab-button");
const registerTabButton = document.getElementById("register-tab-button");
const authStatus = document.getElementById("auth-status");

const nextTarget = resolveNextTarget();

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
    });
});

function switchMode(mode) {
    const isLoginMode = mode === "login";
    loginForm.hidden = !isLoginMode;
    registerForm.hidden = isLoginMode;
    loginTabButton.classList.toggle("is-active", isLoginMode);
    registerTabButton.classList.toggle("is-active", !isLoginMode);
    loginTabButton.setAttribute("aria-selected", String(isLoginMode));
    registerTabButton.setAttribute("aria-selected", String(!isLoginMode));
    authStatus.textContent = isLoginMode
        ? "请输入已有账号进行登录。"
        : "注册成功后会直接进入聊天页面。";
}

async function submitAuthRequest({
    endpoint,
    username,
    password,
    submitButton,
    pendingText,
}) {
    const trimmedUsername = String(username || "").trim();
    const normalizedPassword = String(password || "").trim();
    if (!trimmedUsername || !normalizedPassword) {
        authStatus.textContent = "用户名和密码不能为空。";
        authStatus.classList.add("is-error");
        return;
    }

    submitButton.disabled = true;
    authStatus.textContent = pendingText;
    authStatus.classList.remove("is-error");

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

        authStatus.textContent = "登录成功，正在进入聊天页面…";
        window.location.assign(nextTarget);
    } catch (error) {
        authStatus.textContent = error.message || "登录失败，请稍后重试。";
        authStatus.classList.add("is-error");
    } finally {
        submitButton.disabled = false;
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
