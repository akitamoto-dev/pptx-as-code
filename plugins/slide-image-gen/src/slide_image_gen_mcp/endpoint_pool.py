"""複数 Foundry エンドポイントを束ねるクライアントサイド ロードバランサ。

スライドを連続生成すると単一リージョンの quota（GPT-Image-2 は既定 2/min）を
すぐ使い切るため、複数リージョンのエンドポイントをラウンドロビンで順に使い、
429 や一時エラーが起きたエンドポイントはクールダウンさせて次へフェイルオーバーする。

stdio MCP は MCP クライアントの子プロセスとしてセッション中は常駐するため、次に使う
インデックスや各エンドポイントのクールダウン期限といった状態をプロセス内メモリで保持できる。
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass


def normalize_endpoint(raw: str) -> str:
    """エンドポイント文字列を OpenAI 互換の v1 終端に正規化する。

    ルート（``https://x.services.ai.azure.com/`` や ``https://x.cognitiveservices.azure.com/``）
    でも ``/openai/v1`` 終端でも、いずれも同じ形に揃える。
    """
    url = raw.strip().rstrip("/")
    if not url:
        raise ValueError("空のエンドポイントが指定されました。")
    if not url.endswith("/openai/v1"):
        url = f"{url}/openai/v1"
    return url


@dataclass
class Endpoint:
    """プール内の 1 エンドポイント。"""

    base_url: str
    cooldown_until: float = 0.0  # この epoch 秒までは使用不可

    def is_available(self, now: float) -> bool:
        return now >= self.cooldown_until


class AllEndpointsCoolingDown(RuntimeError):
    """全エンドポイントがクールダウン中で、即時に使えるものが無い。"""

    def __init__(self, wait_seconds: float) -> None:
        self.wait_seconds = max(wait_seconds, 0.0)
        super().__init__(
            f"全リージョンがレート制限中です。約 {self.wait_seconds:.0f} 秒後に再試行してください。"
        )


class EndpointPool:
    """ラウンドロビン + クールダウンでエンドポイントを払い出すプール。"""

    def __init__(self, endpoints: list[str], default_cooldown_seconds: float = 60.0) -> None:
        seen: set[str] = set()
        normalized: list[str] = []
        for raw in endpoints:
            url = normalize_endpoint(raw)
            if url not in seen:
                seen.add(url)
                normalized.append(url)
        if not normalized:
            raise ValueError("エンドポイントが 1 つも指定されていません。")
        # 複数プロセス／セッションが常に同じ順序で同じリージョンへ集中しないよう初期順をシャッフル
        random.shuffle(normalized)
        self._endpoints = [Endpoint(url) for url in normalized]
        self._index = 0
        self._default_cooldown = max(default_cooldown_seconds, 1.0)
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._endpoints)

    def _advance(self) -> int:
        i = self._index
        self._index = (self._index + 1) % len(self._endpoints)
        return i

    def acquire(self) -> Endpoint:
        """使用可能なエンドポイントを 1 つ返す。

        全エンドポイントがクールダウン中なら ``AllEndpointsCoolingDown`` を投げる
        （最短復帰までの待ち秒数を保持する）。
        """
        with self._lock:
            now = time.time()
            for _ in range(len(self._endpoints)):
                ep = self._endpoints[self._advance()]
                if ep.is_available(now):
                    return ep
            soonest = min(ep.cooldown_until for ep in self._endpoints)
            raise AllEndpointsCoolingDown(soonest - now)

    def report_failure(self, endpoint: Endpoint, retry_after: float | None = None) -> None:
        """エンドポイントを一定時間クールダウンさせる（429 / 一時エラー時）。"""
        with self._lock:
            cooldown = retry_after if retry_after is not None else self._default_cooldown
            endpoint.cooldown_until = time.time() + max(cooldown, 1.0)

    def report_success(self, endpoint: Endpoint) -> None:
        """成功したエンドポイントのクールダウンを解除する。"""
        with self._lock:
            endpoint.cooldown_until = 0.0
