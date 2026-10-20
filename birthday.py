# -*- coding: utf-8 -*-
import calendar
import datetime
import json
import os
import time

import requests
from zhdate import ZhDate

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
DATA = os.environ.get("DATA", "")

TODAY = datetime.date.today()
YEAR = TODAY.year
MONTH = TODAY.month

def send_webhook(content):
    if not WEBHOOK_URL:
        print("❌ 错误：没有找到 WEBHOOK_URL 环境变量！")
        return
        
    body = {
        "msgtype": "text",
        "text": {"content": content},
    }
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(WEBHOOK_URL, json=body, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode") == 0:
                print(f"✅ 发送成功:\n{content}\n")
                return
            last_error = result
        except Exception as e:
            last_error = e
        time.sleep(2)
    print(f"❌ 发送最终失败: {last_error}")

def get_lunar_str(month, day):
    """格式化农历文本，例如 8-15 -> 八月十五"""
    cn_num = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    def get_str(n):
        if n <= 10: return cn_num[n]
        if n < 20: return '十' + cn_num[n % 10]
        if n % 10 == 0: return cn_num[n // 10] + '十'
        return cn_num[n // 10] + '十' + cn_num[n % 10]
    
    if day == 10: return f"{get_str(month)}月初十"
    if day == 20: return f"{get_str(month)}月二十"
    if day == 30: return f"{get_str(month)}月三十"
    return f"{get_str(month)}月{cn_num[day] if day < 10 else get_str(day)}"

def lunar_to_solar(lunar_year, month, day):
    """农历转公历，处理腊月三十等边界情况"""
    for candidate_day in (day, day - 1):
        if candidate_day < 1: continue
        try:
            lunar = ZhDate(lunar_year, month, candidate_day)
            solar = ZhDate.to_datetime(lunar).date()
            check = ZhDate.from_datetime(datetime.datetime(solar.year, solar.month, solar.day))
            if check.lunar_year == lunar_year and check.lunar_month == month and check.lunar_day == candidate_day:
                return solar, lunar_year, candidate_day != day
        except Exception:
            continue
    raise ValueError(f"无法转换农历日期: {lunar_year}-{month}-{day}")

def check_monthly_summary(people):
    """功能一：每月 1 号统计本月生日（温柔汇总）"""
    print(f"📅 正在生成 {YEAR}年{MONTH}月 的生日汇总...")
    num_days = calendar.monthrange(YEAR, MONTH)[1]
    month_dates = [datetime.date(YEAR, MONTH, d) for d in range(1, num_days + 1)]
    birthdays_this_month = []

    for item in people:
        name = item["name"]
        year, month, day = (int(x) for x in item["birth"].split("-"))
        found_date, date_desc = None, ""

        if "solar" in item:
            if month == MONTH:
                try:
                    found_date = datetime.date(YEAR, MONTH, day)
                    date_desc = f"公历{MONTH}月{day}日"
                except ValueError:
                    if month == 2 and day == 29 and not calendar.isleap(YEAR):
                        found_date = datetime.date(YEAR, MONTH, 28)
                        date_desc = f"公历{MONTH}月28日(非闰年)"
        else:
            for d_obj in month_dates:
                dt = datetime.datetime(d_obj.year, d_obj.month, d_obj.day)
                lunar = ZhDate.from_datetime(dt)
                if lunar.lunar_month == month and lunar.lunar_day == day:
                    found_date = d_obj
                    date_desc = f"农历{get_lunar_str(month, day)}"
                    break

        if found_date:
            birthdays_this_month.append({"name": name, "date": found_date, "desc": date_desc})

    birthdays_this_month.sort(key=lambda x: x["date"])

    if not birthdays_this_month:
        content = f"🌸 岁月静好 · {YEAR}年{MONTH}月\n\n这个月大家都在忙碌中度过，家里没有人过生日。\n祝愿家人们每一天都平安顺遂、开开心心。"
    else:
        content = f"🌸 岁月如歌 · {YEAR}年{MONTH}月生日名单\n\n在这个美丽的月份里，我们将迎来以下家人的生日：\n\n"
        for b in birthdays_this_month:
            date_str = f"{b['date'].month}月{b['date'].day}日"
            content += f"🎈 {b['name']}：{date_str}（{b['desc']}）\n"
        content += "\n让我们一起期待，提前为寿星们准备好暖暖的祝福吧。"

    send_webhook(content)

def check_daily_advance(people):
    """功能二：每天检查，近期有生日的温柔提醒"""
    print("🔍 正在检查今天和3天后是否有家人生日...")
    TODAY_DT = datetime.datetime(TODAY.year, TODAY.month, TODAY.day)
    CURRENT_LUNAR_YEAR = ZhDate.from_datetime(TODAY_DT).lunar_year
    
    today_messages = []    # 今天的寿星
    upcoming_messages = [] # 近期过生日的家人

    for item in people:
        name = item["name"]
        year, month, day = (int(x) for x in item["birth"].split("-"))

        if "solar" in item:
            try:
                result = datetime.date(TODAY.year, month, day)
            except ValueError:
                result = datetime.date(TODAY.year, month, day - 1)
            if result < TODAY:
                try:
                    result = datetime.date(TODAY.year + 1, month, day)
                except ValueError:
                    result = datetime.date(TODAY.year + 1, month, day - 1)
            adjusted = False
            birthday_year = result.year
        else:
            result, birthday_year, adjusted = lunar_to_solar(CURRENT_LUNAR_YEAR, month, day)
            if result < TODAY:
                result, birthday_year, adjusted = lunar_to_solar(CURRENT_LUNAR_YEAR + 1, month, day)

        flag = (result - TODAY).days
        how_old = birthday_year - year

        # 备注（语气软化）
        note = "（今年腊月没有三十，我们就在廿九这天为您庆祝啦）" if adjusted else ""

        # 当天过生日
        if flag == 0:
            today_messages.append(f"🎂 今天是【{name}】的{how_old}岁生日。{note}\n\n愿岁月温柔以待，祝{name}岁岁平安，健康长寿！🎉")
        
        # 提前 3 天提醒
        elif flag == 3:
            upcoming_messages.append(f"⏳ 还有 3 天：【{name}】的{how_old}岁生日将在 {result.month}月{result.day}日到来啦！{note}")

    # 如果有今天过生日的
    if today_messages:
        content = f"✨ 温馨时刻 · {TODAY}\n\n" + "\n\n".join(today_messages)
        send_webhook(content)
    else:
        print("   - 今天没有家人生日。")

    # 如果有近期过生日的
    if upcoming_messages:
        content = f"🍵 岁月缓缓 · 生日预告\n\n" + "\n".join(upcoming_messages) + "\n\n大家别忘记给寿星送上最暖的祝福哦~"
        send_webhook(content)
    else:
        print("   - 3天后没有家人生日。")

def main():
    if not DATA:
        print("❌ 错误：没有找到 DATA 环境变量！")
        return

    try:
        people = json.loads(DATA)
    except Exception as e:
        print(f"❌ 错误：DATA 环境变量不是合法的 JSON 格式！错误详情: {e}")
        return
    
    # 读取环境变量：如果传了 FORCE_SUMMARY=1，就强制执行汇总（方便测试）
    force_summary = os.environ.get("FORCE_SUMMARY", "0") == "1"
    
    # --- 时间安全锁（防 GitHub 排队到半夜发消息） ---
    # 获取当前北京时间
    now_utc = datetime.datetime.utcnow()
    now_beijing = now_utc + datetime.timedelta(hours=8)
    current_hour = now_beijing.hour

    print(f"⏰ 当前北京时间：{now_beijing.strftime('%Y-%m-%d %H:%M:%S')}")

    if force_summary:
        print("⚠️ 检测到 FORCE_SUMMARY=1，跳过时间锁，强制发送汇总消息！")
    else:
        # 如果不是在早上 7 点到 12 点之间，直接退出，防止半夜发消息
        if current_hour < 7 or current_hour > 12:
            print(f"💤 当前时间 {current_hour} 点，不在 7:00-12:00 提醒时段内，任务静默退出。")
            return

    # 1. 如果是每月 1 号，或者手动强制测试，发本月汇总
    if TODAY.day == 1 or force_summary:
        check_monthly_summary(people)
        
    # 2. 每天检查近期过生日的人 (如果不是强制测试，或者就算强制测试也顺便查一下今天有没有人)
    check_daily_advance(people)

if __name__ == "__main__":
    main()
