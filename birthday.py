# -*- coding: utf-8 -*-
import calendar
import datetime
import json
import os
import time

import requests
from zhdate import ZhDate

WEBHOOK_URL = os.environ["WEBHOOK_URL"]
DATA = os.environ["DATA"]

TODAY = datetime.date.today()
YEAR = TODAY.year
MONTH = TODAY.month

def send_webhook(content):
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
                print(f"发送成功:\n{content}")
                return
            last_error = result
        except Exception as e:
            last_error = e
        time.sleep(2)
    raise RuntimeError(f"发送最终失败: {last_error}")

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
    """功能一：每月 1 号统计本月生日"""
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
        content = f"📅 {YEAR}年{MONTH}月生日汇总\n本月家里没有人生日哦，大家安心工作~"
    else:
        content = f"📅 {YEAR}年{MONTH}月生日汇总\n"
        for b in birthdays_this_month:
            date_str = f"{b['date'].month}月{b['date'].day}日"
            content += f"🎂 {b['name']}：{date_str}（{b['desc']}）\n"
        content += "\n大家记得提前准备祝福和礼物哦！🎁"

    send_webhook(content)

def check_daily_advance(people):
    """功能二：每天检查，提前 7 天（含当天）提醒"""
    TODAY_DT = datetime.datetime(TODAY.year, TODAY.month, TODAY.day)
    CURRENT_LUNAR_YEAR = ZhDate.from_datetime(TODAY_DT).lunar_year
    advance_messages = []

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
        # 提前 7 天触发
        if 0 <= flag <= 7:
            how_old = birthday_year - year
            when = "今天" if flag == 0 else f"{flag}天后"
            note = "（本年该农历月无三十，按廿九提醒）" if adjusted else ""
            advance_messages.append(f"🎂 {name} {result}（{when}）过{how_old}岁生日{note}")

    if advance_messages:
        content = f"📅 {TODAY} 生日预警\n" + "\n".join(advance_messages)
        send_webhook(content)

def main():
    people = json.loads(DATA)
    
    # 1. 如果是每月 1 号，发本月汇总
    if TODAY.day == 1:
        check_monthly_summary(people)
        
    # 2. 每天检查是否有人 7 天内过生日
    check_daily_advance(people)

if __name__ == "__main__":
    main()
