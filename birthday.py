# -*- coding: utf-8 -*-
import datetime
import json
import os
import time

import requests
from zhdate import ZhDate

WEBHOOK_URL = os.environ["WEBHOOK_URL"]
DATA = os.environ["DATA"]

TODAY = datetime.date.today()
TODAY_DT = datetime.datetime(TODAY.year, TODAY.month, TODAY.day)
TODAY_LUNAR = ZhDate.from_datetime(TODAY_DT)
CURRENT_LUNAR_YEAR = TODAY_LUNAR.lunar_year

print(
    f"今天公历 {TODAY}，农历 "
    f"{TODAY_LUNAR.lunar_year}-{TODAY_LUNAR.lunar_month}-{TODAY_LUNAR.lunar_day}"
)


def lunar_to_solar(lunar_year, month, day):
    """
    农历转公历。返回 (公历date, 实际使用的农历年, 是否回退了一天)
    腊月三十在部分年份不存在，自动回退到廿九。
    """
    for candidate_day in (day, day - 1):
        if candidate_day < 1:
            continue
        try:
            lunar = ZhDate(lunar_year, month, candidate_day)
            solar = ZhDate.to_datetime(lunar).date()
            # 反查校验，防止库对无效日期返回错误结果
            check = ZhDate.from_datetime(
                datetime.datetime(solar.year, solar.month, solar.day)
            )
            if (
                check.lunar_year == lunar_year
                and check.lunar_month == month
                and check.lunar_day == candidate_day
            ):
                return solar, lunar_year, candidate_day != day
        except Exception:
            continue
    raise ValueError(f"无法转换农历日期: {lunar_year}-{month}-{day}")


def send_webhook(content):
    body = {
        "msgtype": "text",
        "text": {
            "content": content,
            # 想 @所有人 就取消下面这行注释
            # "mentioned_list": ["@all"]
        },
    }
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(WEBHOOK_URL, json=body, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode") == 0:
                print(f"发送成功: {content}")
                return
            last_error = result
            print(f"第 {attempt + 1} 次发送失败: {result}")
        except Exception as e:
            last_error = e
            print(f"第 {attempt + 1} 次发送异常: {e}")
        time.sleep(2)
    raise RuntimeError(f"群机器人发送最终失败: {last_error}")


def main():
    people = json.loads(DATA)
    for item in people:
        name = item["name"]
        year, month, day = (int(x) for x in item["birth"].split("-"))

        if "solar" in item:
            # 公历生日：取今年或明年最近的一次
            try:
                result = datetime.date(TODAY.year, month, day)
            except ValueError:
                # 处理 2 月 29 日这类非闰年不存在的日期
                result = datetime.date(TODAY.year, month, day - 1)
            if result < TODAY:
                try:
                    result = datetime.date(TODAY.year + 1, month, day)
                except ValueError:
                    result = datetime.date(TODAY.year + 1, month, day - 1)
            adjusted = False
            birthday_year = result.year
        else:
            # 农历生日：先按当前农历年算，过了就用下一农历年
            result, birthday_year, adjusted = lunar_to_solar(
                CURRENT_LUNAR_YEAR, month, day
            )
            if result < TODAY:
                result, birthday_year, adjusted = lunar_to_solar(
                    CURRENT_LUNAR_YEAR + 1, month, day
                )

        flag = (result - TODAY).days
        if flag > 10:
            continue

        how_old = birthday_year - year
        when = "今天" if flag == 0 else f"{flag}天后"
        note = "（本年该农历月无三十，按廿九提醒）" if adjusted else ""

        title = f"{TODAY} 生日提醒"
        content = f"{title}\n{name} {result}（{when}）过{how_old}岁生日{note}"
        send_webhook(content)


if __name__ == "__main__":
    main()
