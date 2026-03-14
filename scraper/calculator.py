from collections import defaultdict

def compute_daily_summary(rows: list[dict]) -> list[dict]:
    """수집된 스냅샷으로 daily_summary 계산"""
    # (course_name, play_date) 기준으로 그룹핑
    groups = defaultdict(list)
    for r in rows:
        key = (r["course_name"], r["play_date"])
        groups[key].append(r)

    summaries = []
    for (course_name, play_date), group in groups.items():
        prices = [r["price_krw"] for r in group if r.get("price_krw")]
        part1 = [r for r in group if r["part_type"] == "1부"]
        part2 = [r for r in group if r["part_type"] == "2부"]
        promos = [r for r in group if r.get("promo_flag")]

        summaries.append({
            "course_id": group[0]["course_id"],
            "course_name": course_name,
            "collected_date": group[0]["collected_date"],
            "play_date": play_date,
            "d_day": group[0]["d_day"],
            "remaining_total": len(group),
            "remaining_part1": len(part1),
            "remaining_part2": len(part2),
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "avg_price": round(sum(prices)/len(prices)) if prices else None,
            "promo_count": len(promos),
            "season": group[0]["season"],
            "weekday_type": group[0]["weekday_type"],
        })
    return summaries
