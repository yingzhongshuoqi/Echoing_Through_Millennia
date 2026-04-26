from __future__ import annotations

import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

import uvicorn


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """测试里保留原始 303 响应，方便验证未登录跳转。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LoginFlowIntegrationTest(unittest.TestCase):
    """覆盖第一阶段登录闭环和最小用户隔离。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls._port = _find_free_port()
        cls._base_url = f"http://127.0.0.1:{cls._port}"
        config = uvicorn.Config(
            "echobot.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=cls._port,
            log_level="warning",
        )
        cls._server = uvicorn.Server(config)
        cls._thread = threading.Thread(target=cls._server.run, daemon=True)
        cls._thread.start()
        _wait_for_server_ready(cls._base_url)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.should_exit = True
        cls._thread.join(timeout=10)

    def test_register_login_logout_and_user_session_isolation(self) -> None:
        """验证注册、登录态、未登录跳转和不同用户会话互不混用。"""

        user_a = f"login_user_a_{time.time_ns()}"
        user_b = f"login_user_b_{time.time_ns()}"
        client_a = _HttpTestClient(self._base_url)
        client_b = _HttpTestClient(self._base_url)

        anonymous_web = client_a.request("GET", "/web")
        self.assertEqual(anonymous_web.status, 303)
        redirect_target = (
            anonymous_web.headers.get("Location")
            or anonymous_web.headers.get("location")
            or ""
        )
        self.assertIn("/login", redirect_target)

        register_a = client_a.request(
            "POST",
            "/api/auth/register",
            {"username": user_a, "password": "Password123"},
        )
        self.assertEqual(register_a.status, 201)

        me_a = client_a.request("GET", "/api/auth/me")
        self.assertEqual(me_a.status, 200)
        self.assertEqual(me_a.json()["username"], user_a)

        config_a = client_a.request("GET", "/api/web/config")
        self.assertEqual(config_a.status, 200)
        self.assertEqual(config_a.json()["session_name"], "default")

        sessions_a_before = client_a.request("GET", "/api/sessions")
        self.assertEqual(sessions_a_before.status, 200)
        self.assertEqual(
            [item["name"] for item in sessions_a_before.json()],
            ["default"],
        )

        create_a_shared = client_a.request(
            "POST",
            "/api/sessions",
            {"name": "shared-demo"},
        )
        self.assertEqual(create_a_shared.status, 200)
        self.assertEqual(create_a_shared.json()["name"], "shared-demo")

        web_after_login = client_a.request("GET", "/web")
        self.assertEqual(web_after_login.status, 200)
        self.assertIn("/web/assets/app.js", web_after_login.text)

        register_b = client_b.request(
            "POST",
            "/api/auth/register",
            {"username": user_b, "password": "Password123"},
        )
        self.assertEqual(register_b.status, 201)

        config_b = client_b.request("GET", "/api/web/config")
        self.assertEqual(config_b.status, 200)
        self.assertEqual(config_b.json()["session_name"], "default")

        sessions_b_before = client_b.request("GET", "/api/sessions")
        self.assertEqual(sessions_b_before.status, 200)
        self.assertEqual(
            [item["name"] for item in sessions_b_before.json()],
            ["default"],
        )

        create_b_shared = client_b.request(
            "POST",
            "/api/sessions",
            {"name": "shared-demo"},
        )
        self.assertEqual(create_b_shared.status, 200)
        self.assertEqual(create_b_shared.json()["name"], "shared-demo")

        sessions_a_after = client_a.request("GET", "/api/sessions")
        sessions_b_after = client_b.request("GET", "/api/sessions")
        self.assertCountEqual(
            [item["name"] for item in sessions_a_after.json()],
            ["shared-demo", "default"],
        )
        self.assertCountEqual(
            [item["name"] for item in sessions_b_after.json()],
            ["shared-demo", "default"],
        )

        current_a = client_a.request("GET", "/api/sessions/current")
        current_b = client_b.request("GET", "/api/sessions/current")
        self.assertEqual(current_a.status, 200)
        self.assertEqual(current_b.status, 200)
        self.assertEqual(current_a.json()["name"], "shared-demo")
        self.assertEqual(current_b.json()["name"], "shared-demo")

        logout_a = client_a.request("POST", "/api/auth/logout")
        self.assertEqual(logout_a.status, 200)

        me_a_after_logout = client_a.request("GET", "/api/auth/me")
        self.assertEqual(me_a_after_logout.status, 401)


class _HttpTestClient:
    """用标准库维持 Cookie，避免给项目额外引入测试依赖。"""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._cookie_jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar),
            _NoRedirectHandler(),
        )

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> "_HttpResponse":
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with self._opener.open(request, timeout=5) as response:
                return _HttpResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    text=response.read().decode("utf-8", errors="replace"),
                )
        except urllib.error.HTTPError as exc:
            return _HttpResponse(
                status=exc.code,
                headers=dict(exc.headers),
                text=exc.read().decode("utf-8", errors="replace"),
            )


class _HttpResponse:
    def __init__(self, *, status: int, headers: dict[str, str], text: str) -> None:
        self.status = status
        self.headers = headers
        self.text = text

    def json(self) -> object:
        return json.loads(self.text)


def _find_free_port() -> int:
    """为集成测试找一个空闲端口，避免和手动启动的服务冲突。"""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_server_ready(base_url: str) -> None:
    """等待临时测试服务启动完成。"""

    last_error: Exception | None = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{base_url}/docs", timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # pragma: no cover - 这里只用于启动等待
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready: {last_error}")
