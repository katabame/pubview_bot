import time
from typing import Any
from riotwatcher import ApiError
from config import lol_watcher, my_region_for_summoner


def get_rank_by_puuid(puuid: str) -> dict[str, Any] | None:
    """PUUIDからランク情報を取得する"""
    max_retries: int = 3
    for attempt in range(max_retries):
        try:
            # LEAGUE-V4のby-puuidエンドポイントを直接呼び出す
            ranked_stats: list[dict[str, Any]] = lol_watcher.league.by_puuid(my_region_for_summoner, puuid)

            # ranked_statsはリスト形式であるため、ループで処理する
            for queue in ranked_stats:
                if queue.get("queueType") == "RANKED_SOLO_5x5":
                    # Solo/Duoランク情報が見つかった場合
                    return {
                        "tier": queue.get("tier"),
                        "rank": queue.get("rank"),
                        "leaguePoints": queue.get("leaguePoints")
                    }

            # リスト内にSolo/Duoランク情報がなかった場合
            return None

        except ApiError as err:
            if err.response.status_code == 429:
                retry_after: int = int(err.response.headers.get('Retry-After', 1))
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_after)
                continue
            elif err.response.status_code == 404:
                # ユーザーにランク情報がない場合
                return None
            else:
                # 400 Bad Requestなど、その他のAPIエラー
                print(f"API Error in get_rank_by_puuid for PUUID {puuid}: {err}")
                raise
        except Exception as e:
            # 予期せぬエラー
            print(f"An unexpected error occurred in get_rank_by_puuid for PUUID {puuid}: {e}")
            raise

    # リトライにすべて失敗した場合
    print(f"Failed to get rank for PUUID {puuid} after {max_retries} retries.")
    return None


def rank_to_value(tier: str, rank: str, lp: int) -> int:
    """ランク情報を数値に変換する（ソート用）"""
    tier_values: dict[str, int] = {"CHALLENGER": 9, "GRANDMASTER": 8, "MASTER": 7, "DIAMOND": 6, "EMERALD": 5, "PLATINUM": 4, "GOLD": 3, "SILVER": 2, "BRONZE": 1, "IRON": 0}
    rank_values: dict[str, int] = {"I": 4, "II": 3, "III": 2, "IV": 1}
    tier_val: int = tier_values.get(tier.upper(), 0) * 1000
    rank_val: int = rank_values.get(rank.upper(), 0) * 100
    return tier_val + rank_val + lp
