#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据抓取脚本：从东方财富获取板块资金流向前8流入+前8流出
输出: data.json (供前端读取)
"""
import json, urllib.request, ssl, os, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

hdr = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/"
}

def fetch(url):
    req = urllib.request.Request(url, headers=hdr)
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    return json.loads(resp.read().decode("utf-8"))

def fetch_flow(code):
    """获取单个板块的分时资金流向"""
    url = f"https://push2.eastmoney.com/api/qt/stock/fflow/KLChart?ut=bd1d9ddb04089700cf9c27f6f7426281&secid=90.{code}&klt=1&lmt=240"
    try:
        data = fetch(url)
        klines = data.get("data", {}).get("klines", [])
        result = []
        for line in klines:
            parts = str(line).split(",")
            dt = parts[0] if len(parts) > 0 else ""
            val = float(parts[1]) / 1e8 if len(parts) > 1 else 0
            time_part = dt.split(" ")[1] if " " in dt else dt
            result.append({"time": time_part, "value": round(val, 1)})
        return result
    except Exception as e:
        print(f"  [WARN] 获取板块 {code} 分时失败: {e}")
        return None

def main():
    base = "https://push2.eastmoney.com/api/qt/clist/get?ut=bd1d9ddb04089700cf9c27f6f7426281"
    fields = "f12,f14,f62"

    # 获取行业 + 概念板块排名
    industry = fetch(f"{base}&pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:2&fields={fields}")
    concept = fetch(f"{base}&pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:3&fields={fields}")

    all_sectors = {}
    for item in (industry.get("data",{}).get("diff",[]) + concept.get("data",{}).get("diff",[])):
        c = item.get("f12","")
        if c:
            name = item.get("f14","")
            net = float(item.get("f62",0)) / 1e8
            if c not in all_sectors:
                all_sectors[c] = {"code": c, "name": name, "net": round(net, 1)}

    slist = sorted(all_sectors.values(), key=lambda x: x["net"], reverse=True)
    inflow = [s for s in slist if s["net"] > 0][:8]
    outflow = [s for s in slist if s["net"] < 0]
    outflow.sort(key=lambda x: x["net"])
    outflow = outflow[:8]

    print(f"净流入板块: {[s['name'] for s in inflow]}")
    print(f"净流出板块: {[s['name'] for s in outflow]}")

    # 抓取每个板块的分时数据 (只抓净流入/流出前各8)
    all_flow = []
    for s in inflow + outflow:
        print(f"获取分时: {s['name']}...")
        flow = fetch_flow(s["code"])
        if flow and len(flow) >= 2:
            all_flow.append({"name": s["name"], "net": s["net"], "flow": flow})
        else:
            print(f"  [SKIP] {s['name']} 无分时数据")

    # 提取时间轴（取数据点最多的板块）
    if not all_flow:
        print("错误: 无任何分时数据")
        sys.exit(1)

    times = max(all_flow, key=lambda x: len(x["flow"]))["flow"]
    times = [t["time"] for t in times]

    # 对齐所有板块到同一时间轴
    for s in all_flow:
        flow_map = {t["time"]: t["value"] for t in s["flow"]}
        last_val = s["net"]
        s["values"] = []
        for t in times:
            if t in flow_map:
                last_val = flow_map[t]
            s["values"].append(round(last_val, 1))

    # 确定Y轴范围
    max_abs = 0
    for s in all_flow:
        for v in s["values"]:
            max_abs = max(max_abs, abs(v))
    y_max = max(max_abs * 1.12, 5)
    y_max = ((y_max + 4.9) // 5) * 5

    output = {
        "tradeDate": all_flow[0]["flow"][0]["date"] if all_flow[0]["flow"] and "date" in all_flow[0]["flow"][0] else "",
        "lastTime": times[-1] if times else "15:00",
        "times": times,
        "sectors": [{"name": s["name"], "net": s["net"], "values": s["values"]} for s in all_flow],
        "yMax": y_max
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n完成! 共 {len(all_flow)} 个板块，数据已保存到 docs/data.json")

if __name__ == "__main__":
    main()
