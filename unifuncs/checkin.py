"""Unifuncs check-in for GitHub Actions; Python standard library only."""
import json
import os
import re
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def run():
    cookie = os.environ.get("UNIFUNCS_COOKIE", "").strip()
    token = re.search(r"(?:^|;)\s*accessToken=([^;]+)", cookie)
    if not token or "\n" in cookie or "\r" in cookie:
        raise ValueError("请配置完整的 UNIFUNCS_COOKIE 密钥，必须包含 accessToken。")
    # Mask individual values as well as the complete Cookie in Actions logs.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::add-mask::" + cookie)
        for part in cookie.split(";"):
            if "=" in part:
                value = part.split("=", 1)[1].strip()
                if value:
                    print("::add-mask::" + value)
    headers = {
        "Cookie": cookie,
        "Authorization": "Bearer " + token.group(1).strip(),
        "Origin": "https://s.unifuncs.com",
        "Referer": "https://s.unifuncs.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "UnifuncsCheckin/1.0",
    }
    opener = build_opener(NoRedirect(), HTTPCookieProcessor(CookieJar()))

    def api(path, post=False):
        request = Request(
            "https://unifuncs.com/platform-api/" + path,
            data=b"{}" if post else None,
            headers={**headers, **({"Content-Type": "application/json"} if post else {})},
            method="POST" if post else "GET",
        )
        try:
            with opener.open(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise ValueError(f"接口返回 HTTP {exc.code}，请检查登录状态或网站限制；未自动重试。") from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("网络请求失败；未自动重试，请查看网站状态。") from None
        except (ValueError, UnicodeError):
            raise ValueError("接口未返回有效 JSON，请检查网站状态。") from None
        if not isinstance(result, dict) or result.get("code") != 0:
            raise ValueError("服务器拒绝本次操作，请检查网站并按需更新 Cookie。")
        data = result.get("data")
        if not isinstance(data, dict):
            raise ValueError("接口数据格式发生变化。")
        return data

    def calendar():
        value = api("check-in/calendar").get("calendar")
        if not isinstance(value, dict) or value.get("enabled") is not True or not isinstance(value.get("checkedInToday"), bool):
            raise ValueError("签到未启用或日历格式发生变化。")
        return value

    today = calendar()
    if today["checkedInToday"]:
        print(f"今天（{today.get('today')}）已签到，连续 {today.get('currentStreak')} 天。")
        return
    result = api("check-in", post=True)
    confirmed = calendar()
    if not confirmed["checkedInToday"]:
        raise ValueError("未确认签到成功，请到网站核对结果后再决定是否重试。")
    print(f"签到成功：{confirmed.get('today')}，奖励 {result.get('rewardAmount')} 积分，连续 {confirmed.get('currentStreak')} 天。")


if __name__ == "__main__":
    try:
        run()
    except ValueError as exc:
        print("执行失败：" + str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("执行失败：出现意外错误，请检查配置和网站状态。", file=sys.stderr)
        sys.exit(1)
