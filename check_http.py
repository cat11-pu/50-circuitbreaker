"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/calls.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    states = []
    for step in spec["ops"]:
        call("POST", base + "/" + step["op"], json.dumps(step).encode())
        states.append(parse(call("GET", base + "/")[1]).get("state"))
    stats = parse(call("GET", base + "/")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("状态轨迹 =", states)
    print("被拒的请求数 =", stats.get("rejected"))
    print("放行的请求数 =", stats.get("allowed"))
    print("半开探测次数 =", stats.get("probe_count"))
    print("最终状态 =", stats.get("state"))
    print("窗口大小 =", stats.get("window"))
    print("失败率阈值（窗口内失败数） =", stats.get("threshold"))
    print("恢复后的状态 =", recovered.get("state"))
    print("不变量（OPEN 期间不放行普通请求） =", spec["open_invariant"])
    print("最小样本数 =", stats.get("min_samples"))
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
